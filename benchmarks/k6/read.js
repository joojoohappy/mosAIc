// B1 read-endpoint load: one URL, closed loop, fixed VUs and iteration count.
// Driven by benchmarks/bench_api.py, which sets TARGET, VUS and ITERATIONS.
import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    read: {
      executor: "shared-iterations",
      vus: Number(__ENV.VUS || 1),
      iterations: Number(__ENV.ITERATIONS || 1000),
      maxDuration: "10m",
    },
  },
  summaryTrendStats: ["min", "med", "avg", "p(95)", "p(99)", "max"],
  discardResponseBodies: true,
};

export default function () {
  const r = http.get(__ENV.TARGET);
  check(r, { "status is 200": (res) => res.status === 200 });
}
