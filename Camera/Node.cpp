// Node.cpp
#include "Node.h"

SocketNode::SocketNode(const std::string& node_name, const std::string& url) : node_name(node_name) {
    // Bind events
    sio_client.set_open_listener(std::bind(&SocketNode::on_connect, this));
    sio_client.set_fail_listener([]() {
        std::cerr << "Socket.IO connection failed" << std::endl;
    });

    // Listen for "get_data" event
    sio_client.socket()->on("get_data", [this](sio::event& ev) {
        // Extract topic and payload from ev.get_message()
        if (ev.get_message()->get_flag() != sio::message::flag_array || ev.get_message()->get_vector().size() < 2) {
            return;
        }

        std::string topic = ev.get_message()->get_vector()[0]->get_string();
        std::string payload = ev.get_message()->get_vector()[1]->get_string();

        std::cout << "Received data on topic '" << topic << "': " << payload << std::endl;

        auto it = topics.find(topic);
        if (it != topics.end()) {
            it->second(payload);
        }
    });
    
    // Listen for shutdown
    sio_client.socket()->on("shutdown", [this](sio::event& ev) {
        this->on_shutdown();
    });

    try_connect(url);
}

SocketNode::~SocketNode() {
    sio_client.sync_close();
    sio_client.clear_con_listeners();
}

void SocketNode::on_connect() {
    std::cout << "Node " << node_name << " connected" << std::endl;
    connected = true;
    sio_client.socket()->emit("connect_node", node_name);
}

void SocketNode::on_get_data(const std::string& name, sio::message::ptr const& data,
                       bool need_ack, sio::message::ptr& ack_message) {
    if (data->get_flag() != sio::message::flag::flag_array || data->get_vector().size() < 2) {
        return;
    }

    std::string topic = data->get_vector()[0]->get_string();
    std::string payload = data->get_vector()[1]->get_string();

    std::cout << "Received data on topic '" << topic << "': " << payload << std::endl;

    auto it = topics.find(topic);
    if (it != topics.end()) {
        it->second(payload);
    }
}

void SocketNode::on_shutdown() {
    std::cout << "Shutting down node" << std::endl;
    std::exit(0);
}

void SocketNode::try_connect(const std::string& url) {
    try {
        sio_client.connect(url);
    } catch (const std::exception& e) {
        std::cerr << "Socket.IO connection error: " << e.what() << std::endl;
    }
}

void SocketNode::send(const std::string& topic, const std::string& data) {
    if (!connected) {
        std::cerr << "Node not connected!" << std::endl;
        return;
    }

    std::cout << "Sending data (" << data << ") to topic: (" << topic << ")" << std::endl;

    sio::message::ptr msg_array = sio::array_message::create();
    
    // Use get_vector() — this works in almost all versions
    auto& vec = msg_array->get_vector();
    vec.push_back(sio::string_message::create(topic));
    vec.push_back(sio::string_message::create(data));

    sio_client.socket()->emit("send_data", msg_array);
}

void SocketNode::subscribe(const std::string& topic, std::function<void(const std::string&)> function) {
    if (!connected) {
        std::cerr << "Node not connected!" << std::endl;
        return;
    }

    sio_client.socket()->emit("join_topic", topic);
    topics[topic] = function;
}

void SocketNode::emit(const std::string& event) {
    if (!connected) {
        std::cerr << "Node not connected!" << std::endl;
        return;
    }
    sio_client.socket()->emit(event);
}
