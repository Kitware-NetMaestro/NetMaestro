# NetMaestro webinar demo

This branch (`webinar-demo`) is the NetMaestro instance shown in the webinar. Follow these
steps to run it on your own machine. It comes with finished FABRIC runs already loaded, so
you can explore results right away and run your own simulations when you want to.

## What you need

- **Docker** with Compose v2 (Docker Desktop on macOS or Windows, or Docker Engine with the
  Compose plugin on Linux). Check with `docker compose version`.
- **git**.
- A browser with internet access. The pages load their JavaScript and styles from public
  CDNs.
- Free local ports **8000** (web app), **5432** (Postgres), **5672/15672** (RabbitMQ) and
  **9000/9001** (MinIO).

## 1. Get the code

```sh
git clone https://github.com/Kitware-NetMaestro/netmaestro.git
cd netmaestro
git checkout webinar-demo
```

## 2. Build and start the stack

```sh
docker compose build
docker compose up -d
```

The first build compiles MPICH, ROSS, CODES and the fluid-flow WAN (FFW) simulation
models from source, so it takes a while. Later starts reuse the built image and take
seconds.

`docker compose up -d` starts five containers:

| Service | What it does |
|---|---|
| `django` | The web app, at http://localhost:8000 |
| `celery` | The worker that runs simulations and ingests their results |
| `postgres` | The database |
| `rabbitmq` | The queue between the web app and the worker |
| `minio` | File storage for simulation output |

Check that they are all up with `docker compose ps`.

## 3. Set up the database and load the demo runs

```sh
docker compose exec django ./manage.py migrate
docker compose exec django ./manage.py load_demo
```

`load_demo` loads the runs stored in `data/webinar/`. It runs no simulations and takes
about 15 seconds. It's safe to run again; anything already loaded is skipped. You should
see:

```
Run 1: loaded 'FABRIC baseline'
Ensemble 1: loaded 'FABRIC buffer vs bottleneck' with 6 members
```

## 4. Open NetMaestro

Go to **http://localhost:8000**.

---

## What's preloaded

All of the runs use the **Fluid Flow WAN FABRIC 5 Site** topology: a five-site cut of the
FABRIC testbed core (LOSA, SALT, STAR, NEWY, MICH). The TeraCore ring links run at
1.2 Tbps. MICH connects to the rest of the network through a single 100 Gbps link to STAR,
which makes STAR–MICH the bottleneck. Each site has a 2 Gb shared switch buffer and two
100 Gbps terminals.

Traffic is **random**: 100–300 Gb flows between all ten terminals for 12 s, then the
network drains. The random seed is fixed, so re-running any of these configurations gives
the same numbers.

### A single run: "FABRIC baseline"

The published FABRIC configuration, run once. To view it, go to **Sidebar → Results** and
select **FABRIC baseline**. On the **Network Performance** tab, press **Play** to watch
STAR→MICH saturate while the TeraCore links stay quiet.

### An ensemble: "FABRIC buffer vs bottleneck"

A six-member parameter sweep that asks: *at the MICH site, which does more to limit
dropped traffic, deeper switch buffers or a faster STAR–MICH link?*

| Member | Switch buffer | STAR–MICH link | Dropped (Mbit) |
|---|---|---|---|
| 1 | 2 Gb | 40 Gbps | 188,692 |
| 2 *(baseline)* | 2 Gb | 100 Gbps | 269,693 |
| 3 | 2 Gb | 400 Gbps | 327,820 |
| 4 | 8 Gb | 40 Gbps | 156,122 |
| 5 | 8 Gb | 100 Gbps | 193,801 |
| 6 | 8 Gb | 400 Gbps | 245,625 |

Go to **Sidebar → Ensembles** and open the ensemble. From top to bottom, the detail page
shows:

- **Tiles**: the best member and the range across members for each headline metric.
- **Compare members**: a parallel-coordinates plot with one line per member. Drag along
  an axis to filter the members. Hovering over a row in the table highlights that
  member's line.
- **Members table**: every member's parameters and metrics. Turn on **Δ vs baseline**
  to see each member's difference from member 2.
- **Compare selected**: tick two or more rows, then pick a switch or link and a metric to
  plot them over time. For example, tick members 1 and 4 and plot **STAR** buffer
  occupancy.
- **Sweep curve** and **Effect of each parameter**: the same results plotted as one line
  per link bandwidth, and as a buffer × bandwidth table.
- **Export CSV** (top right): one row per member, ready for a notebook.
- **Analyze** on any member opens it in the single-run Results page.

---

## Run your own simulations

The worker runs real FFW simulations, and each FABRIC run takes a few seconds.

**A single run:** go to **Sidebar → Simulation** (or **Topology → Run a Simulation**),
pick a topology and traffic mode, then click **Save and Run**. Results appear under
**Results** when the run shows ✓.

**A sweep:** go to **Sidebar → Ensembles → New Ensemble**. Choose a base configuration,
then add sweep parameters with **Add parameter… → Add**. For a link bandwidth parameter,
pick the link before typing values. The card shows how many members the sweep makes. Click
**Save and Run**, and the members run one after another.

**Custom components:** under **Sidebar → Available Models → Fluid Flow WAN → Get Started**
you can save a switch with your own buffer and bandwidth defaults, then use it when you
edit a topology.

---

## Stopping, restarting and resetting

| To… | Run |
|---|---|
| Stop, keeping your data | `docker compose down` |
| Start again | `docker compose up -d` |
| Delete everything and start fresh | `docker compose down -v`, then steps 2–3 again |

## Troubleshooting

| Symptom | Fix |
|---|---|
| A container won't start because a port is in use | Stop whatever else is using that port (often a local Postgres on 5432), then run `docker compose up -d` again |
| http://localhost:8000 shows a database error | You skipped `migrate`. Run step 3 |
| The Ensembles or Results pages are empty | Run `docker compose exec django ./manage.py load_demo` |
| New runs stay *Pending* | The worker isn't running. Run `docker compose up -d celery` and check `docker compose logs celery` |
| Pages look unstyled | The browser can't reach the CDNs (cdn.jsdelivr.net, esm.sh). Check your network or proxy |

For more about the project, see [README.md](README.md). Development setup is in
[DEVELOPMENT.md](DEVELOPMENT.md).
