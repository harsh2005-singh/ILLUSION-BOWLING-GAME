# Illusion Bowling

A bowling game built on an optical illusion. The ramp and the lane are two separate
pieces, hidden far apart along one line of sight. Seen through an orthographic camera
(no perspective) from exactly the right angle, they look like one connected track.
Rotate the view until the pieces join, then roll. Look from any other angle and you can
see the ball hop between them.

## Play online
https://harsh2005-singh.github.io/ILLUSION-BOWLING-GAME/

Works in any modern browser on desktop and mobile. Drag to rotate, and use the
sliders for aim and spin.

## Levels
| Level | Name | What changes |
|---|---|---|
| 1 | First Light | 6 pins, a wide lane, a forgiving angle, unlimited hints |
| 2 | Other Side | The secret angle moves to a different side, 10 pins, 3 hints |
| 3 | Narrow Gauge | A thin lane, tighter alignment, 2 hints |
| 4 | Sliding Rack | The pins slide side to side, 1 hint |
| 5 | Needle's Eye | A very narrow lane, a very tight angle, fast-sliding pins, no hints and no closeness meter |

Each level asks you to knock down a set number of pins within 3 rolls. Winning earns up
to 3 stars, plus bonus points for rolls you didn't need.

## Controls
| Input | Action |
|---|---|
| Mouse drag or touch drag | Rotate the view (release near the angle and it snaps) |
| Arrow keys | Rotate the view |
| A / D | Aim left / right |
| Z / X | Spin left / right |
| Space | Roll (only works when the track looks joined) |
| H | Hint (animates to the correct angle, limited per level) |
| R | Restart the level |

## Two versions in this repo
- **`index.html`**: the web version, a single file using three.js. This is what the
  link above serves.
- **`main.py`**: the desktop version, written with Python and pygame-ce.

## Run the web version locally
Open `index.html` in your browser, or start a small server:
```
py -m http.server 8000
```
Then open http://localhost:8000.

## Run the desktop version
```
py -m pip install pygame-ce
py main.py
```

## Built with
- Web: HTML, CSS, JavaScript and three.js, hosted on GitHub Pages
- Desktop: Python and pygame-ce
