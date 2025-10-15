# mlat-server Docker usage

## Build and run (localhost)

- Build image and start with workdir bound to host:

```
# Build
docker compose build

# Run
docker compose up -d

# Logs
docker logs -f mlat-server
```

This exposes the JSON client on localhost:40147 and binds `./workdir` so files like `aircraft.json`, `clients.json`, and `sync.json` persist on the host.

The entrypoint rebuilds Cython extensions on every container start.

## One-off docker run (without compose)

```
docker build -t mlat-server:local .
docker run --rm -it \
  -p 40147:40147 \
  -v $(pwd)/workdir:/app/workdir \
  mlat-server:local \
  --work-dir ./workdir \
  --client-listen 0.0.0.0:40147 \
  --status-interval 10
```

## VPS notes

- Open TCP port 40147 in your firewall/security group.
- Ensure the container runs with the same volume mapping so `workdir` persists.
- To update to latest code, rebuild the image or mount your repo and let entrypoint rebuild on start.

```bash
docker compose pull && docker compose build && docker compose up -d
```

## Troubleshooting

- If Cython build fails, ensure `build-essential` and `python3-dev` are installed (the image already has them).
- If `pygraphviz` fails, you may need Graphviz system libs; this repo may not require pygraphviz at runtime. Remove from pip install if unnecessary.
- Check server binary path is `./mlat-server/mlat-server`. If not executable, set `chmod +x mlat-server/mlat-server`.