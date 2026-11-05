# BenchBase CH-benCHmark

The article uses BenchBase commit `33c00473807ebd49304d114a6d769d2d2b2bbb34`
with the PostgreSQL profile. The checked-in configuration runs scale factor 1,
warms up for 10 seconds, and measures a mixed TPC-C/CH-benCHmark workload for
60 seconds.

The raw run is intentionally kept separate from RASH measurements. BenchBase
does not measure replication freshness, so its OLTP p99 and OLAP p95 values
must not be converted into a complete RASH candidate by inventing a freshness
value.

Run the following commands from the repository root. Clone the exact BenchBase
revision and build its PostgreSQL distribution with the same JDK 23 image used
for the recorded experiment:

```sh
BENCHBASE_WORK=$(mktemp -d)
git clone https://github.com/cmu-db/benchbase.git "$BENCHBASE_WORK/source"
git -C "$BENCHBASE_WORK/source" checkout 33c00473807ebd49304d114a6d769d2d2b2bbb34

docker run --rm \
  -v "$BENCHBASE_WORK/source:/src" \
  -w /src \
  maven@sha256:6df31244c87c5107dd2c3f62f5634e5cb3cddedbb99b07cb8778284f576c2646 \
  sh -lc 'git config --global --add safe.directory /src && mvn -q -DskipTests clean package -P postgres'

mkdir -p "$BENCHBASE_WORK/dist"
tar -xzf "$BENCHBASE_WORK/source/target/benchbase-postgres.tgz" \
  -C "$BENCHBASE_WORK/dist" --strip-components=1
```

Start a dedicated PostgreSQL 17 container on port 55432 with enough predicate
locks for the analytical queries:

```sh
docker run -d --rm --name rash-benchbase-postgres \
  -p 55432:5432 \
  -e POSTGRES_DB=benchbase \
  -e POSTGRES_USER=benchbase \
  -e POSTGRES_PASSWORD=benchbase \
  postgres:17.6 \
  -c max_pred_locks_per_transaction=1024 \
  -c max_pred_locks_per_relation=1024
```

The checked-in JDBC URL uses `host.docker.internal` because the recorded runs
executed BenchBase in the JDK container. Prepare an output directory and run
the composite benchmark. Create and load the schema only for the first run:

```sh
mkdir -p results/benchbase/rerun

docker run --rm --user "$(id -u):$(id -g)" \
  --add-host=host.docker.internal:host-gateway \
  -v "$BENCHBASE_WORK/dist:/bench:ro" \
  -v "$(pwd)/benchmarks/benchbase/postgres-chbenchmark.xml:/config.xml:ro" \
  -v "$(pwd)/results/benchbase/rerun:/results" \
  -w /bench \
  maven@sha256:6df31244c87c5107dd2c3f62f5634e5cb3cddedbb99b07cb8778284f576c2646 \
  java -jar benchbase.jar -b tpcc,chbenchmark -c /config.xml \
  --create=true --load=true --execute=true -d /results/run-1
```

Repeat the last `docker run` command for `run-2` and `run-3`, replacing the
final arguments with `--create=false --load=false --execute=true` and the
corresponding output directory. Stop the dedicated database after the
experiment with `docker stop rash-benchbase-postgres`; the `--rm` option
removes that container while leaving result files untouched.

Use `htap_ranker.benchbase.summarize_benchbase_run` on each matching
`*.raw.csv` and `*.summary.json` pair. Latencies are converted from
microseconds to milliseconds; Q1 through Q22 are classified as OLAP and the
five TPC-C transaction types as OLTP.
