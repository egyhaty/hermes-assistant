# syntax=docker/dockerfile:1
# Build only after selecting immutable upstream and Codex versions. No defaults
# intentionally: a tag such as latest must not silently determine production code.
ARG HERMES_BASE_IMAGE
FROM ${HERMES_BASE_IMAGE}
USER root
COPY container/security-pins.json container/patch_dependencies.py /opt/karem-build/
RUN apt-get update && apt-get install -y --no-install-recommends --only-upgrade libbrotli1 && rm -rf /var/lib/apt/lists/*
RUN python3 /opt/karem-build/patch_dependencies.py && \
    python3 -c 'import json,subprocess; pins=json.load(open("/opt/karem-build/security-pins.json"))["python"]; subprocess.run(["/opt/hermes/tools/uv-0.13.5-linux-x64/uv","pip","install","--python","/opt/hermes/.venv/bin/python","--no-deps"]+[k+"=="+v for k,v in pins.items()],check=True)'
# The sealed runtime uses PM/uv; remove the unused interpreter pip installer
# and its outdated vendored dependencies/SBOM rather than suppress their findings.
RUN rm -rf /opt/hermes/tools/python-3.14.9+20261021-linux-x64/lib/python3.14/site-packages/pip \
    /opt/hermes/tools/python-3.14.9+20261021-linux-x64/lib/python3.14/site-packages/pip-26.2.2.dist-info
# Upstream exports placeholder distribution metadata although the CLI/release
# is v0.22.5. Record the real, verified release in that metadata.
RUN python3 -c 'import shutil; from pathlib import Path; p=Path("/opt/hermes/hermes_agent-0.0.0.dist-info/METADATA"); s=p.read_text(); assert "Version: 0.0.0\n" in s; p.write_text(s.replace("Version: 0.0.0\n","Version: 0.22.5\n",1)); shutil.move(str(p.parent),str(p.parent.with_name("hermes_agent-0.22.5.dist-info")))'
ARG CODEX_VERSION
RUN test -n "$CODEX_VERSION" && npm install --prefix /usr/local -g "@openai/codex@${CODEX_VERSION}" && npm cache clean --force
COPY --chown=0:0 config/SOUL.md /opt/karem/config/SOUL.md
COPY --chown=0:0 skills /opt/karem/skills
COPY --chown=0:0 scripts /opt/karem/scripts
COPY --chown=0:0 docs /opt/karem/docs
RUN chmod -R a+rX,go-w /opt/karem && \
    test -x /opt/hermes/.venv/bin/hermes && \
    test -x /opt/hermes/.venv/bin/python && \
    test "$(id -u hermes)" = "10000" && \
    codex --version
ENV HERMES_HOME=/opt/data
ENV HOME=/opt/data
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /opt/hermes
USER 10000:10000
# Bypass the official image's root/s6 bootstrap intentionally. Our own bootstrap
# seeds only project configuration; Kubernetes supplies UID and volume ownership.
ENTRYPOINT ["/opt/hermes/.venv/bin/python", "/opt/karem/scripts/bootstrap.py", "--exec"]
