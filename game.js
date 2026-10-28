(() => {
  "use strict";

  // ---- Canvas setup ----
  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const W = canvas.width;   // 808
  const H = canvas.height;  // 663

  const GROUND_H = 70;
  const PLAY_H = H - GROUND_H; // playable sky height

  // ---- Assets ----
  const ghostImg = new Image();
  ghostImg.src = "assets/ghosty.png";

  const jumpSound = new Audio("assets/jump.wav");
  const gameOverSound = new Audio("assets/game_over.wav");
  jumpSound.volume = 0.5;
  gameOverSound.volume = 0.6;

  function playSound(sound) {
    try {
      sound.currentTime = 0;
      sound.play().catch(() => {});
    } catch (e) {
      /* ignore audio errors */
    }
  }

  // ---- Tunables ----
  const GRAVITY = 0.45;
  const FLAP_VELOCITY = -8.2;
  const MAX_FALL = 12;

  const PIPE_WIDTH = 78;
  const PIPE_CAP_H = 28;
  const PIPE_GAP = 190;      // vertical opening
  const PIPE_SPACING = 260;  // horizontal distance between pipes
  const PIPE_SPEED = 2.8;
  const PIPE_MARGIN = 70;    // keep gap away from top/ground

  const GHOST_W = 46;
  const GHOST_H = 46;
  const GHOST_X = W * 0.28;

  // ---- Game state ----
  const STATE = { READY: "ready", PLAYING: "playing", DEAD: "dead" };
  let state = STATE.READY;

  let ghost, pipes, score, frame;
  let highScore = Number(localStorage.getItem("flappyKiroHigh") || 0);

  // Decorative background clouds
  const clouds = [];

  function makeCloud(x) {
    return {
      x: x,
      y: 40 + Math.random() * (PLAY_H - 160),
      w: 70 + Math.random() * 60,
      h: 44 + Math.random() * 26,
      speed: 0.3 + Math.random() * 0.4,
    };
  }

  function initClouds() {
    clouds.length = 0;
    for (let i = 0; i < 6; i++) {
      clouds.push(makeCloud(Math.random() * W));
    }
  }

  function reset() {
    ghost = { x: GHOST_X, y: PLAY_H / 2, vy: 0, rot: 0 };
    pipes = [];
    score = 0;
    frame = 0;
    // seed first pipes off-screen to the right
    let startX = W + 120;
    for (let i = 0; i < 4; i++) {
      pipes.push(makePipe(startX + i * PIPE_SPACING));
    }
  }

  function makePipe(x) {
    const minGapY = PIPE_MARGIN + PIPE_GAP / 2;
    const maxGapY = PLAY_H - PIPE_MARGIN - PIPE_GAP / 2;
    const gapY = minGapY + Math.random() * (maxGapY - minGapY);
    return { x: x, gapY: gapY, scored: false };
  }

  // ---- Input ----
  function flap() {
    if (state === STATE.READY) {
      startGame();
      return;
    }
    if (state === STATE.PLAYING) {
      ghost.vy = FLAP_VELOCITY;
      playSound(jumpSound);
    }
  }

  function startGame() {
    reset();
    state = STATE.PLAYING;
    hideOverlay(overlayEl);
    hideOverlay(gameOverEl);
    ghost.vy = FLAP_VELOCITY;
    playSound(jumpSound);
  }

  function die() {
    if (state !== STATE.PLAYING) return;
    state = STATE.DEAD;
    playSound(gameOverSound);
    if (score > highScore) {
      highScore = score;
      localStorage.setItem("flappyKiroHigh", String(highScore));
    }
    finalScoreEl.textContent = score;
    finalHighEl.textContent = highScore;
    showOverlay(gameOverEl);
  }

  // ---- Update ----
  function update() {
    frame++;

    // clouds always drift
    for (const c of clouds) {
      c.x -= c.speed;
      if (c.x + c.w < 0) {
        c.x = W + Math.random() * 80;
        c.y = 40 + Math.random() * (PLAY_H - 160);
      }
    }

    if (state !== STATE.PLAYING) return;

    // ghost physics
    ghost.vy = Math.min(ghost.vy + GRAVITY, MAX_FALL);
    ghost.y += ghost.vy;
    ghost.rot = Math.max(-0.35, Math.min(1.0, ghost.vy / 12));

    // pipes
    for (const p of pipes) {
      p.x -= PIPE_SPEED;

      // scoring: when ghost passes pipe center
      if (!p.scored && p.x + PIPE_WIDTH < ghost.x) {
        p.scored = true;
        score++;
      }
    }

    // recycle / spawn pipes
    if (pipes.length && pipes[0].x + PIPE_WIDTH < -20) {
      pipes.shift();
    }
    const last = pipes[pipes.length - 1];
    if (last && last.x < W - PIPE_SPACING) {
      pipes.push(makePipe(last.x + PIPE_SPACING));
    }

    // collisions
    checkCollisions();
  }

  function checkCollisions() {
    // ground / ceiling
    if (ghost.y + GHOST_H / 2 >= PLAY_H) {
      ghost.y = PLAY_H - GHOST_H / 2;
      die();
      return;
    }
    if (ghost.y - GHOST_H / 2 <= 0) {
      ghost.y = GHOST_H / 2;
      ghost.vy = 0;
    }

    // Use a slightly forgiving hitbox for the ghost
    const hb = {
      left: ghost.x - GHOST_W / 2 + 6,
      right: ghost.x + GHOST_W / 2 - 6,
      top: ghost.y - GHOST_H / 2 + 6,
      bottom: ghost.y + GHOST_H / 2 - 4,
    };

    for (const p of pipes) {
      const pl = p.x;
      const pr = p.x + PIPE_WIDTH;
      if (hb.right < pl || hb.left > pr) continue; // not horizontally aligned

      const gapTop = p.gapY - PIPE_GAP / 2;
      const gapBottom = p.gapY + PIPE_GAP / 2;
      if (hb.top < gapTop || hb.bottom > gapBottom) {
        die();
        return;
      }
    }
  }

  // ---- Render ----
  function drawBackground() {
    // sky gradient (light blue, painterly feel)
    const sky = ctx.createLinearGradient(0, 0, 0, PLAY_H);
    sky.addColorStop(0, "#9fd4ea");
    sky.addColorStop(1, "#7cc1e4");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, PLAY_H);

    // subtle sketchy texture streaks
    ctx.save();
    ctx.globalAlpha = 0.06;
    ctx.strokeStyle = "#3f6f90";
    ctx.lineWidth = 2;
    for (let i = 0; i < 22; i++) {
      const x = (i * 53 + (frame * 0.2)) % W;
      ctx.beginPath();
      ctx.moveTo(x, 20 + (i % 5) * 30);
      ctx.lineTo(x + 8, PLAY_H - 40 - (i % 7) * 20);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawClouds() {
    ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
    for (const c of clouds) {
      roundRect(ctx, c.x, c.y, c.w, c.h, 18);
      ctx.fill();
    }
  }

  function drawPipe(p) {
    const gapTop = p.gapY - PIPE_GAP / 2;
    const gapBottom = p.gapY + PIPE_GAP / 2;

    const bodyGrad = ctx.createLinearGradient(p.x, 0, p.x + PIPE_WIDTH, 0);
    bodyGrad.addColorStop(0, "#4ea32e");
    bodyGrad.addColorStop(0.5, "#5fbf39");
    bodyGrad.addColorStop(1, "#3f8a26");

    const capGrad = ctx.createLinearGradient(p.x, 0, p.x + PIPE_WIDTH, 0);
    capGrad.addColorStop(0, "#3f8a26");
    capGrad.addColorStop(0.5, "#54ad33");
    capGrad.addColorStop(1, "#357322");

    const capOverhang = 6;

    // top pipe
    ctx.fillStyle = bodyGrad;
    ctx.fillRect(p.x, 0, PIPE_WIDTH, gapTop - PIPE_CAP_H);
    ctx.fillStyle = capGrad;
    ctx.fillRect(p.x - capOverhang, gapTop - PIPE_CAP_H, PIPE_WIDTH + capOverhang * 2, PIPE_CAP_H);

    // bottom pipe
    ctx.fillStyle = bodyGrad;
    ctx.fillRect(p.x, gapBottom + PIPE_CAP_H, PIPE_WIDTH, PLAY_H - (gapBottom + PIPE_CAP_H));
    ctx.fillStyle = capGrad;
    ctx.fillRect(p.x - capOverhang, gapBottom, PIPE_WIDTH + capOverhang * 2, PIPE_CAP_H);

    // outlines for a crisp retro edge
    ctx.strokeStyle = "rgba(30, 70, 20, 0.35)";
    ctx.lineWidth = 2;
    ctx.strokeRect(p.x - capOverhang, gapTop - PIPE_CAP_H, PIPE_WIDTH + capOverhang * 2, PIPE_CAP_H);
    ctx.strokeRect(p.x - capOverhang, gapBottom, PIPE_WIDTH + capOverhang * 2, PIPE_CAP_H);
  }

  function drawGhost() {
    ctx.save();
    ctx.translate(ghost.x, ghost.y);
    ctx.rotate(ghost.rot);
    if (ghostImg.complete && ghostImg.naturalWidth > 0) {
      ctx.drawImage(ghostImg, -GHOST_W / 2, -GHOST_H / 2, GHOST_W, GHOST_H);
    } else {
      // fallback ghost shape until image loads
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(0, 0, GHOST_W / 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#000";
      ctx.beginPath();
      ctx.ellipse(-7, -3, 4, 6, 0, 0, Math.PI * 2);
      ctx.ellipse(7, -3, 4, 6, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawGround() {
    const g = ctx.createLinearGradient(0, PLAY_H, 0, H);
    g.addColorStop(0, "#464f5e");
    g.addColorStop(1, "#353d4a");
    ctx.fillStyle = g;
    ctx.fillRect(0, PLAY_H, W, GROUND_H);

    // top edge highlight
    ctx.fillStyle = "rgba(255,255,255,0.08)";
    ctx.fillRect(0, PLAY_H, W, 3);
  }

  function drawScore() {
    ctx.save();
    ctx.font = "bold 26px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const text = `Score: ${score} | High: ${highScore}`;
    const y = PLAY_H + GROUND_H / 2;
    ctx.lineWidth = 4;
    ctx.strokeStyle = "rgba(0,0,0,0.5)";
    ctx.strokeText(text, W / 2, y);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(text, W / 2, y);
    ctx.restore();
  }

  function render() {
    drawBackground();
    drawClouds();
    for (const p of pipes) drawPipe(p);
    drawGhost();
    drawGround();
    drawScore();
  }

  // ---- Helpers ----
  function roundRect(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // ---- Main loop ----
  function loop() {
    update();
    render();
    requestAnimationFrame(loop);
  }

  // ---- Overlay elements ----
  const overlayEl = document.getElementById("overlay");
  const gameOverEl = document.getElementById("gameover");
  const startBtn = document.getElementById("start-btn");
  const restartBtn = document.getElementById("restart-btn");
  const finalScoreEl = document.getElementById("final-score");
  const finalHighEl = document.getElementById("final-high");

  function showOverlay(el) { el.classList.remove("hidden"); }
  function hideOverlay(el) { el.classList.add("hidden"); }

  startBtn.addEventListener("click", (e) => { e.stopPropagation(); startGame(); });
  restartBtn.addEventListener("click", (e) => { e.stopPropagation(); startGame(); });

  // Pointer + keyboard input on the game area
  canvas.addEventListener("pointerdown", (e) => { e.preventDefault(); flap(); });
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" || e.code === "ArrowUp") {
      e.preventDefault();
      if (state === STATE.DEAD) {
        startGame();
      } else {
        flap();
      }
    }
  });

  // ---- Boot ----
  initClouds();
  reset();
  loop();
})();
