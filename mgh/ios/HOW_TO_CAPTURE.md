# Capture test: no laptop, no server (about 10 minutes)

Use the Fuga app from the `mgh-localization` branch (installed with Xcode).

1. Open **Camera test settings & export** and make sure the **Server URL is empty**.
2. Select **Floor 4**. Type or say **440**.
3. Pick 3–4 different spots on floor 4 near 416, 430 and 440, for example: in front of the 430 sign, halfway down the hallway, at the 440 sign, near 416.
4. At each spot:
   - Hold the phone upright, pointing down the hallway (doors, corners and signs in view help).
   - Tap **Look again** and hold still for about 3 seconds. The status should stay "Not located yet". That's expected.
   - Tap **Share camera test** and AirDrop or privately message the file to the project owner (not GitHub).
   - Write one line: `spot 1: in front of the 430 sign, facing the doors`.
5. Send all the files and the lines together.

The project owner then runs `localization/replay_capture_route.py` on them. It draws the green route and arrow onto each photo, showing what the app would have done there. That shows the system's guess for a person who stood there to judge; it doesn't prove accuracy.
