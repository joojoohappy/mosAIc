
### B1 read endpoints — baseline

| Endpoint | Conc. | p50 ms | p95 ms | p99 ms | req/s | server CPU (cores) |
|---|---|---|---|---|---|---|
| `GET /api/health` | 1 | 0.66 (0.59–0.71) | 0.95 (0.91–1.08) | 1.36 (1.34–1.40) | 1264 (1176–1394) | 0.54 (0.51–0.56) |
| `GET /api/health` | 8 | 2.89 (2.57–3.02) | 5.24 (4.96–5.45) | 7.55 (7.42–9.01) | 2344 (2125–2503) | 0.59 (0.58–0.60) |
| `GET /api/health` | 32 | 10.86 (10.70–11.80) | 18.29 (15.98–18.46) | 35.39 (31.45–36.60) | 2543 (2450–2648) | 0.58 (0.56–0.59) |
| `GET /api/recipes` | 1 | 1.02 (0.95–1.02) | 1.42 (1.39–1.89) | 2.27 (1.73–8.99) | 876 (720–916) | 0.66 (0.60–0.66) |
| `GET /api/recipes` | 8 | 8.67 (7.99–8.85) | 14.67 (13.76–15.46) | 18.45 (16.71–19.04) | 868 (841–936) | 0.94 (0.94–0.95) |
| `GET /api/recipes` | 32 | 33.20 (33.11–33.67) | 50.88 (49.70–54.72) | 68.16 (63.24–78.10) | 916 (914–918) | 0.96 (0.96–0.97) |
| `GET /api/recipes/{id}` | 1 | 0.94 (0.91–0.97) | 1.32 (1.23–1.32) | 1.84 (1.75–2.39) | 932 (914–967) | 0.67 (0.63–0.67) |
| `GET /api/recipes/{id}` | 8 | 8.75 (8.24–8.96) | 14.36 (14.02–15.51) | 18.34 (16.89–20.03) | 865 (833–903) | 0.96 (0.94–0.96) |
| `GET /api/recipes/{id}` | 32 | 32.29 (31.62–35.20) | 48.08 (46.42–58.77) | 55.91 (52.51–77.47) | 952 (861–964) | 0.94 (0.92–0.94) |
| `GET /api/results/{id}` | 1 | 0.87 (0.81–0.91) | 1.51 (1.21–1.73) | 3.04 (2.53–3.42) | 920 (908–1034) | 0.61 (0.59–0.62) |
| `GET /api/results/{id}` | 8 | 8.10 (7.45–8.13) | 13.21 (12.79–14.49) | 16.25 (16.19–20.79) | 934 (893–981) | 0.90 (0.86–0.94) |
| `GET /api/results/{id}` | 32 | 29.68 (26.84–32.93) | 40.74 (39.55–47.23) | 59.52 (46.85–62.94) | 1054 (935–1116) | 0.95 (0.88–0.96) |
| `GET /static/results/{name}` | 1 | 0.88 (0.84–0.90) | 1.27 (1.20–1.45) | 1.72 (1.66–2.23) | 1003 (954–1028) | 0.57 (0.56–0.59) |
| `GET /static/results/{name}` | 8 | 9.63 (8.35–10.40) | 14.56 (13.93–17.39) | 18.29 (17.21–21.36) | 800 (724–888) | 0.99 (0.95–1.03) |
| `GET /static/results/{name}` | 32 | 34.45 (33.66–35.54) | 51.89 (47.65–54.85) | 60.32 (53.81–78.70) | 873 (869–918) | 1.05 (1.05–1.08) |

### B2 generate overhead — baseline (simulated provider, 0 s)

| Photo | Upload MB | p50 ms | p95 ms | server CPU ms/req |
|---|---|---|---|---|
| 0.3MP 640x480 | 0.12 | 8.7 (7.2–9.0) | 11.0 (9.8–11.9) | 5.6 (4.7–5.7) |
| 3MP 2048x1536 | 1.24 | 25.2 (25.1–26.0) | 34.0 (33.2–35.2) | 21.5 (21.0–21.8) |
| 12MP 4032x3024 | 4.81 | 79.9 (79.5–79.9) | 109.2 (109.2–110.6) | 75.2 (75.1–76.3) |

| Burst (MAX_CONCURRENT=2, model 2 s) | Statuses | Provider calls | Served p50 ms | Slowest 503 ms |
|---|---|---|---|---|
| 10 | {'503': 8, '200': 2} | 2 | 2141.5 | 85.9 |
| 20 | {'503': 18, '200': 2} | 2 | 2160.0 | 123.2 |

| In flight (7.6 MB uploads, model 1 s) | Idle RSS MB | Peak RSS MB | Growth MB |
|---|---|---|---|
| 1 | 51.4 | 94.6 | 43.2 |
| 4 | 51.5 | 205.6 | 154.1 |
| 16 | 51.4 | 534.5 | 483.1 |

### B3 reliability — baseline (simulated provider, timeout 2 s)

| Provider behaviour | HTTP | mode | fallbackReason | wall s |
|---|---|---|---|---|
| ok | 200 | live | None | 0.15 |
| error | 200 | mock | provider_error | 0.13 |
| hang | 200 | mock | provider_timeout | 2.1 |
| text | 200 | mock | provider_no_image | 0.09 |
| badjson | 200 | mock | provider_no_image | 0.12 |
| drip | 200 | live | None | 12.63 |
| refused | 200 | mock | provider_error | 0.14 |

| Duplicate case | Provider calls | Same resultId |
|---|---|---|
| simultaneous | 2 | False |
| 1s apart (refresh + retry) | 2 | False |
| after first finished | 1 | True |

| Budget race (limit 50, 300 requests, 16 clients) | Provider calls per trial | HTTP 500s per trial |
|---|---|---|
| 1 worker(s) | [50, 50, 50, 50, 50] | [0, 0, 0, 0, 0] |
| 4 worker(s) | [50, 50, 73, 50, 51] | [1, 1, 2, 2, 0] |

| Damaged upload | HTTP | reached provider |
|---|---|---|
| jpeg truncated to 99% | 200 | True |
| jpeg truncated to 90% | 200 | True |
| jpeg truncated to 50% | 200 | True |
| jpeg truncated to 10% | 200 | True |
| jpeg truncated to 1% | 200 | True |
| jpeg 20KB zeroed mid-file | 200 | True |
| valid jpeg (control) | 200 | True |

Rate limit, 6 forged X-Forwarded-For: [200, 200, 200, 429, 429, 429]  
Daily budget 5, 8 requests: [200, 200, 200, 200, 200, 503, 503, 503], provider calls 5  
Body limits: {'declared_9MB': [413, '{"error":"too_large"}'], 'chunked_9MB': [400, '{"detail":"There was an error parsing th'], 'health_after': 200}  
Restart: {'restart_to_healthy_s': {'sigterm': 0.5, 'sigkill': 0.42}, 'result_after_sigterm': 200, 'result_after_sigkill': 200}

### B2b stage timing — baseline

| Photo | Stage | median ms | p95 ms |
|---|---|---|---|
| 0.3MP | validate_upload | 0.027 | 0.034 |
| 0.3MP | fingerprint_sha256 | 0.332 | 0.447 |
| 0.3MP | build_request_json | 0.63 | 1.109 |
| 3MP | validate_upload | 0.029 | 0.049 |
| 3MP | fingerprint_sha256 | 3.63 | 5.544 |
| 3MP | build_request_json | 6.394 | 9.891 |
| 12MP | validate_upload | 0.028 | 0.045 |
| 12MP | fingerprint_sha256 | 13.324 | 17.658 |
| 12MP | build_request_json | 23.197 | 29.308 |
| - | load_recipes (per request) | 0.048 | 0.078 |

### B1 read endpoints — after

| Endpoint | Conc. | p50 ms | p95 ms | p99 ms | req/s | server CPU (cores) |
|---|---|---|---|---|---|---|
| `GET /api/health` | 1 | 0.60 (0.56–0.68) | 0.86 (0.85–0.99) | 1.31 (1.09–1.96) | 1341 (1198–1462) | 0.51 (0.50–0.54) |
| `GET /api/health` | 8 | 2.71 (2.57–2.83) | 5.39 (5.05–5.40) | 7.70 (6.99–8.58) | 2534 (2421–2599) | 0.58 (0.55–0.58) |
| `GET /api/health` | 32 | 11.84 (10.45–12.19) | 16.72 (16.27–17.40) | 24.12 (18.14–24.23) | 2617 (2442–2763) | 0.58 (0.56–0.65) |
| `GET /api/recipes` | 1 | 1.05 (0.95–1.12) | 1.60 (1.32–1.64) | 2.06 (2.03–3.13) | 829 (762–932) | 0.67 (0.62–0.69) |
| `GET /api/recipes` | 8 | 8.73 (8.04–9.97) | 15.09 (12.72–17.09) | 19.53 (15.68–20.93) | 854 (754–949) | 0.91 (0.88–0.94) |
| `GET /api/recipes` | 32 | 31.41 (29.33–35.80) | 49.78 (45.60–51.70) | 72.57 (66.84–78.53) | 945 (873–1025) | 0.90 (0.86–0.92) |
| `GET /api/recipes/{id}` | 1 | 0.83 (0.73–0.84) | 1.24 (1.02–1.25) | 1.78 (1.51–2.05) | 1035 (1025–1193) | 0.60 (0.58–0.67) |
| `GET /api/recipes/{id}` | 8 | 7.42 (7.24–8.01) | 12.33 (11.72–13.83) | 14.53 (14.41–17.03) | 1010 (918–1040) | 0.94 (0.88–0.95) |
| `GET /api/recipes/{id}` | 32 | 26.36 (24.68–27.82) | 39.97 (36.81–40.80) | 53.00 (45.53–53.71) | 1140 (1099–1237) | 0.85 (0.81–0.88) |
| `GET /api/results/{id}` | 1 | 0.90 (0.85–0.90) | 1.37 (1.34–1.40) | 2.46 (2.24–2.60) | 942 (940–997) | 0.62 (0.57–0.64) |
| `GET /api/results/{id}` | 8 | 7.88 (7.36–8.58) | 13.52 (12.27–14.29) | 18.35 (16.15–19.47) | 941 (872–999) | 0.91 (0.88–0.94) |
| `GET /api/results/{id}` | 32 | 28.01 (25.78–30.15) | 42.15 (36.56–46.06) | 46.00 (44.57–81.67) | 1100 (994–1198) | 0.92 (0.82–0.93) |
| `GET /static/results/{name}` | 1 | 0.83 (0.82–0.86) | 1.23 (1.14–1.45) | 2.01 (1.87–2.53) | 1028 (955–1038) | 0.57 (0.57–0.62) |
| `GET /static/results/{name}` | 8 | 9.62 (9.32–10.24) | 15.29 (14.71–15.91) | 17.74 (16.81–19.79) | 789 (750–819) | 0.99 (0.98–1.04) |
| `GET /static/results/{name}` | 32 | 36.78 (35.98–37.02) | 53.79 (52.43–59.40) | 63.71 (60.50–81.52) | 848 (830–872) | 1.01 (0.99–1.05) |

### B2 generate overhead — after (simulated provider, 0 s)

| Photo | Upload MB | p50 ms | p95 ms | server CPU ms/req |
|---|---|---|---|---|
| 0.3MP 640x480 | 0.12 | 11.2 (10.7–11.3) | 14.0 (13.9–14.3) | 7.8 (7.6–8.0) |
| 3MP 2048x1536 | 1.24 | 38.9 (37.6–40.8) | 51.2 (49.9–51.5) | 34.8 (33.3–35.7) |
| 12MP 4032x3024 | 4.81 | 132.3 (131.0–133.6) | 166.0 (165.4–166.1) | 127.0 (126.9–127.7) |

| Burst (MAX_CONCURRENT=2, model 2 s) | Statuses | Provider calls | Served p50 ms | Slowest 503 ms |
|---|---|---|---|---|
| 10 | {'503': 8, '200': 2} | 2 | 2148.2 | 96.3 |
| 20 | {'503': 18, '200': 2} | 2 | 2144.4 | 110.9 |

| In flight (7.6 MB uploads, model 1 s) | Idle RSS MB | Peak RSS MB | Growth MB |
|---|---|---|---|
| 1 | 51.5 | 95.2 | 43.7 |
| 4 | 51.5 | 206.7 | 155.2 |
| 16 | 51.5 | 492.9 | 441.4 |

### B3 reliability — after (simulated provider, timeout 2 s)

| Provider behaviour | HTTP | mode | fallbackReason | wall s |
|---|---|---|---|---|
| ok | 200 | live | None | 0.14 |
| error | 200 | mock | provider_error | 0.11 |
| hang | 200 | mock | provider_timeout | 2.08 |
| text | 200 | mock | provider_no_image | 0.11 |
| badjson | 200 | mock | provider_no_image | 0.1 |
| drip | 200 | mock | provider_timeout | 2.07 |
| refused | 200 | mock | provider_error | 0.09 |

| Duplicate case | Provider calls | Same resultId |
|---|---|---|
| simultaneous | 1 | True |
| 1s apart (refresh + retry) | 1 | True |
| after first finished | 1 | True |

| Budget race (limit 50, 300 requests, 16 clients) | Provider calls per trial | HTTP 500s per trial |
|---|---|---|
| 1 worker(s) | [50, 50, 50, 50, 50] | [0, 0, 0, 0, 0] |
| 4 worker(s) | [51, 53, 53, 53, 52] | [0, 0, 0, 0, 0] |

| Damaged upload | HTTP | reached provider |
|---|---|---|
| jpeg truncated to 99% | 400 | False |
| jpeg truncated to 90% | 400 | False |
| jpeg truncated to 50% | 400 | False |
| jpeg truncated to 10% | 400 | False |
| jpeg truncated to 1% | 400 | False |
| jpeg 20KB zeroed mid-file | 200 | True |
| valid jpeg (control) | 200 | True |

Rate limit, 6 forged X-Forwarded-For: [200, 200, 200, 429, 429, 429]  
Daily budget 5, 8 requests: [200, 200, 200, 200, 200, 503, 503, 503], provider calls 5  
Body limits: {'declared_9MB': [413, '{"error":"too_large"}'], 'chunked_9MB': [400, '{"detail":"There was an error parsing th'], 'health_after': 200}  
Restart: {'restart_to_healthy_s': {'sigterm': 0.53, 'sigkill': 0.42}, 'result_after_sigterm': 200, 'result_after_sigkill': 200}

### B2b stage timing — after

| Photo | Stage | median ms | p95 ms |
|---|---|---|---|
| 0.3MP | validate_upload | 1.281 | 1.335 |
| 0.3MP | fingerprint_sha256 | 0.306 | 0.322 |
| 0.3MP | build_request_json | 0.552 | 0.609 |
| 3MP | validate_upload | 12.567 | 16.106 |
| 3MP | fingerprint_sha256 | 3.292 | 3.665 |
| 3MP | build_request_json | 5.865 | 8.308 |
| 12MP | validate_upload | 50.287 | 56.226 |
| 12MP | fingerprint_sha256 | 13.34 | 17.446 |
| 12MP | build_request_json | 24.157 | 29.061 |
| - | load_recipes (per request) | 0.055 | 0.119 |
