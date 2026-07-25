FROM rust:1.88.0-bookworm@sha256:4727898c104ecd2e22d780925832502faee9fe4e70581b8572af081370b315a0 AS core-build

WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY shared/rust/md2docx-core/ shared/rust/md2docx-core/
RUN cargo build --locked --release --package md2docx-core --bin md2docx-core-cli

FROM python:3.12.11-slim-bookworm@sha256:47ae396f09c1303b8653019811a8498470603d7ffefc29cb07c88f1f8cb3d19f

ARG DEBIAN_SNAPSHOT=20250701T000000Z

RUN rm -f /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
       "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}/ bookworm main" \
       "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}/ bookworm-security main" \
       > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install --no-install-recommends -y \
       fonts-dejavu-core \
       fonts-liberation \
       fonts-noto-core \
       libreoffice-writer \
       poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY requirements-dev.txt ./
RUN python -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version" \
    && python -m pip install --no-cache-dir -r requirements-dev.txt

COPY products/skill-one/skill-one/ products/skill-one/skill-one/
COPY scripts/generate_readme_examples.py scripts/validate_visual_regression.py scripts/
COPY tests/visual/expected-sha256.json tests/visual/expected-sha256.json
COPY --from=core-build /src/target/release/md2docx-core-cli products/skill-one/skill-one/bin/md2docx-core-linux-x64

RUN chmod +x products/skill-one/skill-one/bin/md2docx-core-linux-x64 \
    && python -c "import hashlib,json,pathlib; p=pathlib.Path('products/skill-one/skill-one/assets/runtime-manifest.json'); d=json.loads(p.read_text()); b=pathlib.Path('products/skill-one/skill-one/bin/md2docx-core-linux-x64'); d['binaries']['bin/md2docx-core-linux-x64']=hashlib.sha256(b.read_bytes()).hexdigest(); p.write_text(json.dumps(d, indent=2) + '\n')"

ENTRYPOINT ["python", "scripts/validate_visual_regression.py"]
