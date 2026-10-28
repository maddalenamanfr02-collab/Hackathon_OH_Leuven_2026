# Flappy Kiro 👻

A retro, browser-based endless scroller where you guide a ghost through a set of
green pipes. Built with plain HTML5 Canvas, CSS, and JavaScript — no build step,
no dependencies.

Made for the **Hackathon OH Leuven 2026**.

## How to play

- **Click**, **tap**, or press **Space** / **↑** to flap.
- Keep the ghost in the air and fly through the gaps between the pipes.
- Each pipe you clear scores a point. Hitting a pipe or the ground ends the run.
- Your best score is saved locally in the browser.

## Run it locally

Because the game loads image and audio assets, serve the folder over HTTP rather
than opening the file directly:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000> in your browser.

## Project structure

| Path | Description |
| --- | --- |
| `index.html` | Game page: canvas and start / game-over overlays |
| `style.css` | Retro styling for the frame, overlays, and score panel |
| `game.js` | Game engine: physics, pipes, scoring, input, rendering |
| `assets/` | Ghost sprite (`ghosty.png`) and sound effects (`jump.wav`, `game_over.wav`) |
| `img/` | Screenshots and reference images |

## Gameplay details

- Gravity pulls the ghost down; each flap gives it an upward boost.
- Pipes scroll endlessly from right to left with randomized gap positions.
- `jump.wav` plays on each flap and `game_over.wav` plays on a crash.
- The score and all-time high (`Score: X | High: Y`) are shown on the ground strip.
- The high score persists between sessions via `localStorage`.

## Tuning

Gameplay constants live at the top of `game.js` and are easy to tweak:
`GRAVITY`, `FLAP_VELOCITY`, `PIPE_GAP`, `PIPE_SPEED`, and `PIPE_SPACING`.
