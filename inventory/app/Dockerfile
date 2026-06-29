# /app/Dockerfile
# Stage 1: Build the Rust Binary
FROM rust:1.75-alpine AS builder
WORKDIR /usr/src/aegis-app
RUN apk add --no-cache musl-dev
COPY Cargo.toml .
COPY src ./src
RUN cargo build --release

# Stage 2: Minimal Production Image
FROM alpine:latest
WORKDIR /opt/aegis
COPY --from=builder /usr/src/aegis-app/target/release/aegis-telematics-app .
EXPOSE 3000
CMD ["./aegis-telematics-app"]