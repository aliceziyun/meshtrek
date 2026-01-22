import http from "k6/http";

export const options = {
  scenarios: {
    burst: {
      executor: "ramping-arrival-rate",
      startRate: 500,
      timeUnit: "1s",
      preAllocatedVUs: 200,
      maxVUs: 4000,
      stages: [
        { target: 500,  duration: "10s" }, // steady
        { target: 2000, duration: "10s" }, // burst
        { target: 500,  duration: "10s" }, // recovery
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  http.get(__ENV.URL);
}

