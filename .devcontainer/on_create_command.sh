#! /usr/bin/env bash

# some color definitions
C_GRAY="\e[90m"
#C_LGRAY="\e[37m"
#C_CYAN="\e[36m"
C_LCYAN="\e[96m"
C_LGREEN="\e[92m"
C_RESET="\e[0m"

# as the devcontainer logs parallel activities we need to mark the output of this script for easier debugging
SCRIPT_MARKER="${C_GRAY}[.devcontainer/on_create_command.sh] $C_RESET"

title() {
    echo -e "$SCRIPT_MARKER$C_LCYAN$1$C_RESET"
}

info() {
    echo -e "$SCRIPT_MARKER$C_LGREEN$1$C_RESET"
}

run_with_marker() {
    # Run the command given by "$@".
    # Redirect stderr into a loop that reads each line and prints it (with the marker) to stderr.
    # Pipe stdout through a similar loop that writes to stdout.
    "$@" 2> >(while IFS= read -r line; do
                echo -e "${SCRIPT_MARKER}${line}" >&2
            done) | while IFS= read -r line; do
                echo -e "${SCRIPT_MARKER}${line}"
            done
    # Return the exit code of the executed command (the first element of PIPESTATUS).
    return "${PIPESTATUS[0]}"
}

title "Running OnCreateCommand script..."

info "Installing poetry dependencies..."
run_with_marker poetry install

info "Installing pre-commit hooks..."
run_with_marker pre-commit install --install-hooks
