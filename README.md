# Illusion Bowling

A bowling game built on an optical illusion. The ramp and the lane are two separate
pieces hidden far apart along one line of sight. Seen through an orthographic camera
from exactly the right angle, they look like one connected track. Rotate the view
until they join, then roll.

5 levels: narrower lanes, tighter angles, sliding pins, and no hints at the end.

## Play online
https://harsh2005-singh.github.io/ILLUSION-BOWLING-GAME/

## Run locally
```
py -m pip install pygame-ce
py main.py
```

## Controls
| Key | Action |
|---|---|
| Mouse drag / arrow keys | Rotate the view (release near the angle to snap) |
| A / D | Aim |
| Z / X | Spin |
| SPACE | Roll (only when the track looks joined) |
| H | Hint |
| R | Restart level |

## Built with
Python, pygame-ce, and pygbag for the web build.
