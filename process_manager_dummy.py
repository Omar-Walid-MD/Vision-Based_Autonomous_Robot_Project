#!/usr/bin/env python3

"""
Dummy CLI Process Manager Simulator
----------------------------------
- Left panel: process list with colored status
- Right panel: live output of selected process
- Bottom: key controls
"""

import curses
import time
import random
import threading

# Names of dummy processes to simulate
PROCESS_NAMES = ["Server", "Simulation", "Camera", "Voice", "Sensors"]

# Mapping of process status to colors for display
STATUS_COLORS = {
    "running": curses.COLOR_GREEN,
    "stopped": curses.COLOR_RED,
    "restarting": curses.COLOR_YELLOW,
}

# Flag to indicate that the UI needs to be redrawn
needs_redraw = True  # force initial draw

class DummyProcess:
    """Simulates a process with status and log output."""
    def __init__(self, name):
        self.name = name
        self.status = "running"          # current status of the process
        self.output = []                  # list of output log strings
        self._alive = True                # control flag for background log simulation
        # Start a background thread to simulate log generation
        self._thread = threading.Thread(target=self._simulate_output, daemon=True)
        self._thread.start()

    def _simulate_output(self):
        """Continuously generate dummy log messages while process is running."""
        while self._alive:
            if self.status == "running":
                msg = f"[{self.name}] Log event: {random.randint(100,999)}"
                self.output.append(msg)
                if len(self.output) > 50:  # keep only last 50 messages
                    self.output.pop(0)
            time.sleep(random.uniform(0.5, 1.5))  # random delay between logs

    def restart(self):
        """Simulate restarting the process."""
        global needs_redraw
        self.status = "restarting"
        self.output.append(f"[{self.name}] Restarting...")
        needs_redraw = True
        time.sleep(0.5)  # simulate restart delay
        self.status = "running"
        self.output.append(f"[{self.name}] Restarted.")
        needs_redraw = True

    def kill(self):
        """Stop the process and log it."""
        self.status = "stopped"
        self.output.append(f"[{self.name}] Killed.")

    def stop(self):
        """Stop background log simulation thread."""
        self._alive = False


def draw_process_list(stdscr, processes, selected):
    """Draw the left panel showing process names and their status."""
    h, w = stdscr.getmaxyx()
    win = stdscr.derwin(h - 2, w//3, 0, 0)  # panel size and position
    win.box()
    win.addstr(0, 2, " Processes ")

    # Draw each process name with color and highlight the selected one
    for i, p in enumerate(processes):
        display_str = f"{p.name:<12} ({p.status})"
        if i == selected:
            win.attron(curses.A_REVERSE)  # highlight selected process
        color_pair = 1 if p.status == "running" else 2 if p.status == "stopped" else 3
        win.attron(curses.color_pair(color_pair))
        win.addstr(i+1, 2, display_str.ljust(w//3 - 4))
        win.attroff(curses.color_pair(color_pair))
        if i == selected:
            win.attroff(curses.A_REVERSE)

    win.noutrefresh()  # mark for refresh without immediate redraw


def draw_output_panel(stdscr, process):
    """Draw the right panel showing logs of the selected process."""
    h, w = stdscr.getmaxyx()
    win = stdscr.derwin(h - 2, (2*w)//3, 0, w//3)  # panel size and position
    win.box()
    title = f" Output - {process.name} "
    win.addstr(0, 2, title)

    # Display last (h-4) lines of logs
    start_line = max(0, len(process.output) - (h - 4))
    for i, line in enumerate(process.output[start_line:]):
        win.addstr(i+1, 1, line[:w-4])

    win.refresh()  # redraw the output panel immediately


def draw_controls(stdscr):
    """Draw the bottom panel showing available key controls."""
    h, w = stdscr.getmaxyx()
    win = stdscr.derwin(2, w, h-2, 0)
    win.addstr(0, 0, "[↑/↓: Navigate]  [R: Restart]  [K: Kill]  [Ctrl+A: Restart All]  [Q: Quit]")
    win.refresh()


def main(stdscr):
    """Main function running the CLI process manager."""
    curses.curs_set(0)  # hide cursor
    curses.noecho()     # don't display pressed keys
    curses.cbreak()     # respond to keys instantly
    stdscr.keypad(True) # interpret special keys like arrows

    # Initialize color pairs for status highlighting
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    # Create dummy processes
    processes = [DummyProcess(name) for name in PROCESS_NAMES]
    selected = 0  # currently selected process

    while True:
        stdscr.clear()
        draw_process_list(stdscr, processes, selected)
        draw_output_panel(stdscr, processes[selected])
        draw_controls(stdscr)
        stdscr.refresh()

        try:
            key = stdscr.get_wch()
        except curses.error:
            key = None  # no key pressed

        if key is not None:
            # Mark screen for redraw on any key press
            needs_redraw = True

        if needs_redraw:
            draw_process_list(stdscr, processes, selected)
            draw_output_panel(stdscr, processes[selected])
            draw_controls(stdscr)
            curses.doupdate()  # refresh all panels at once
            needs_redraw = False

        # Handle key actions
        if key == 450:  # UP arrow
            selected = (selected - 1) % len(processes)
        elif key == 456:  # DOWN arrow
            selected = (selected + 1) % len(processes)
        elif key in ('q', 'Q'):  # Quit
            break
        elif key in ('r', 'R'):  # Restart selected process
            threading.Thread(target=processes[selected].restart, daemon=True).start()
        elif key in ('k', 'K'):  # Kill selected process
            processes[selected].kill()
        elif key == '': # Ctrl+A -> restart all processes
            for p in processes:
                threading.Thread(target=p.restart, daemon=True).start()

    # Stop all background threads before exiting
    for p in processes:
        p.stop()


if __name__ == "__main__":
    curses.wrapper(main)
