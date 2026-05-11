FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

# default shell = zsh
SHELL [ "/bin/zsh", "-c" ]

# set environment
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV_DISABLE_PROMPT=1
ENV TZ=Europe/Berlin
ENV PATH="/root/.local/bin:/home/vscode/.local/bin:${PATH}"

# configure git (at system lever)
# - set git default branch name to "main"
# - trust all workspace directories - this is primarily needed for windows support,
#   because for the workspace bind-mount the executing user (vscode) isn't the filesystem owner (root)
RUN git config --system init.defaultBranch main \
    && git config --system --add safe.directory '*'

# install gitleaks
RUN DOWNLOAD_URL=$(curl -s "https://api.github.com/repos/gitleaks/gitleaks/releases/latest" \
    | jq -r '.assets[] | select(.name | contains("linux_x64")) | .browser_download_url') \
    && curl -sL "$DOWNLOAD_URL" | tar -xzf - -C /usr/local/bin gitleaks \
    && chmod +x /usr/local/bin/gitleaks

# Switch to vscode user
USER vscode

# Install poetry (we're not use pipx here because poetry in a virtualenv has it's issues...)
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && mkdir -p ~/.zfunc \
    && poetry completions zsh > ~/.zfunc/_poetry \
    && echo 'fpath+=~/.zfunc' >> ~/.zshrc \
    && echo 'autoload -Uz compinit && compinit' >> ~/.zshrc

# Install precommit globally in the container (with pipx installation we had error messages during pre-commit
# checks like "/usr/local/bin/python: No module named pre_commit" - seems it needs the python module available
# in the global python environment
RUN pipx install pre-commit && \
    pipx install pre-commit-hooks

# Install poethepoet (task runner for poetry)
RUN pipx install poethepoet

# inject + install QA tooling (+ type stubs for mypy for pyyaml and requests)
RUN pipx upgrade --install mypy \
    && pipx inject mypy types-PyYAML types-requests \
    && pipx install ruff \
    && pipx install commitizen \
    && pipx install reuse \
    && pipx install yamllint \
    && pipx install cyclonedx-bom \
    && pipx install sbom2doc

# note that installation of dependencies and pre-commit installation will be done after vscode has started
# the container.
