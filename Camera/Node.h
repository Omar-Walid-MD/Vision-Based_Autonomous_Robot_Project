// Node.h
#ifndef NODE_H
#define NODE_H

#include <sio_client.h>
#include <sio_socket.h>
#include <functional>
#include <string>
#include <map>
#include <thread>
#include <iostream>
#include <cstdlib> // for exit

class SocketNode {
public:
    SocketNode(const std::string& node_name, const std::string& url = "http://localhost:5000");
    ~SocketNode();

    void send(const std::string& topic, const std::string& data);
    void subscribe(const std::string& topic, std::function<void(const std::string&)> callback);
    void emit(const std::string& event);

private:
    sio::client sio_client;
    sio::socket::ptr current_socket;
    std::string node_name;
    std::map<std::string, std::function<void(const std::string&)>> topics;
    bool connected = false;

    void on_connect();
    void on_get_data(const std::string& name, sio::message::ptr const& data, bool need_ack, sio::message::ptr& ack_message);
    void on_shutdown();
    void try_connect(const std::string& url);
};

#endif // NODE_H
