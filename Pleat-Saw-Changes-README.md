Pleat Saw Current State (2025-12-11)
====================================

Scope
-----
- Captures the current behavior and key changes made during the Dec 10–11 session.
- Applies to the Pi deployment at `/home/ambf1/pleat_saw` (Git repo pushed to `git@github.com:capceri/AMBF-Pleat-Saw.git`, branch `master`).

Key Functional Changes
----------------------
- M2 manual jog safety:
  - Forward jog is blocked if S3 is active; reverse jog is blocked if S2 is active.
  - While jogging, the background loop stops motion immediately if S3 (fwd) or S2 (rev) activates.
- M2 default speeds:
  - Forward: 40 mm/s; Reverse: 60 mm/s (config/motion.yaml).
- M2 status indicators:
  - Engineering dashboard now shows S2/S3 (and optional S4) using live IO inputs, so indicators light when switches are pressed.
- Clamp / cycle behavior:
  - Clamp is forced ON during START_SPINDLE and FEED_FWD; releases in COMPLETE.
  - Air_jet (Valve 2) remains mapped to CH2 and functions.
- Blade start timeout handling:
  - In START_SPINDLE, if the ESP32-A does not report `RUN` before `m1_start_timeout` (3s), the supervisor now proceeds to FEED_FWD with a warning (avoids TIMEOUT_BLADE_START alarm).

Current Config Highlights
-------------------------
- Motion (`config/motion.yaml`):
  - `m1_blade.timeout_start_s: 3.0`
  - `m2_fixture.default_speed_mm_s: 40.0`
  - `m2_fixture.default_speed_rev_mm_s: 60.0`
  - Other cycle timing values are unchanged from the restored baseline.
- IO map (`config/io_map.yaml`):
  - clamp → CH1 / bit0 (Valve 1 on RS-485 IO module)
  - air_jet → CH2 / bit1 (Valve 2 on RS-485 IO module)
- System (`config/system.yaml`):
  - RS-485 IO module on `/dev/ttySC0`, slave ID 1, 9600,N,8,1 (module must respond on this bus).

Code Touch Points
-----------------
- `app/services/supervisor.py`
  - START_SPINDLE: clamp ON; m1_start retried every 0.5s; if RUN seen → FEED_FWD; if timeout elapsed without RUN → warning then FEED_FWD (no alarm).
  - FEED_FWD: clamp ON; starts feed forward; stops on S3 then DWELL; TIMEOUT_FWD alarm if timeout exceeded.
  - FEED_REV: clamp ON; starts feed reverse; stops on S2 then CLAMP; TIMEOUT_REV alarm if timeout exceeded.
  - COMPLETE: releases clamp after cycle (existing behavior preserved).
- `app/services/web_monitor.py`
  - Manual jog forward/reverse refuse to start if S3/S2 active.
  - Runtime jog stop: if jogging forward and S3 trips, or jogging reverse and S2 trips, M2 stops immediately.
  - M2 fixture status overlayed with IO inputs for at_s2/at_s3/(optional at_s4) so dashboard indicators reflect switches.
- `config/motion.yaml`
  - Updated M2 default speeds to 40/60.
- `app/web/templates/engineering.html` and `dashboard.html`
  - Output label for CH2 reads “Chute Clear (CH2)” (uses `air_jet` key under the hood).

Repository / Deployment
-----------------------
- Pi repo path: `/home/ambf1/pleat_saw`
- Git remote: `git@github.com:capceri/AMBF-Pleat-Saw.git`
- Branch: `master` (tracking origin)
- Last commits on Pi:
  - `22bd907` Proceed to feed if blade RUN not reported after timeout.
  - `4a03f43` Keep clamp engaged through start and feed_fwd; release at complete.
  - `7f2fe8f` Enforce M2 manual jog limits using S2/S3 stop logic.
  - `070bf0a` Update manual jog limits; adjust M2 default speeds to 40/60.
  - `14640d6` Baseline after session_backup_20251126 restore.

Behavior Summary (expected)
---------------------------
- Auto cycle:
  1) Clamp ON, blade start issued.
  2) If ESP32 reports RUN, or after 3s without RUN, proceed to FEED_FWD.
  3) Feed forward until S3 → DWELL, then FEED_REV until S2 → CLAMP → SAW_STOP → AIR_JET → COMPLETE (clamp releases).
- Manual jog:
  - Forward jog inhibited if S3 active; reverse jog inhibited if S2 active; jogging stops immediately if limits trip.
- Dashboard indicators:
  - S2/S3 (and optional S4) reflect real IO input state.

Open Risks / Notes
------------------
- ESP32-A status may not emit `RUN` while the blade spins; cycle now proceeds after timeout to avoid stalling.
- RS-485 IO module must be reachable on `/dev/ttySC0` slave 1; verify wiring/power if outputs appear stuck.
- Clamp/air_jet remain mapped to CH1/CH2; ensure the module output commons are wired to the valve supply.
