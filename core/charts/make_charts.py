from pathlib import Path
import matplotlib.pyplot as plt

def chart_top_movers_png(output_dir: Path, items):
    output_dir.mkdir(parents=True, exist_ok=True)
    p = output_dir / "top_movers.png"
    tickers = [t for t, _ in items]
    moves = [m for _, m in items]

    plt.figure()
    plt.bar(tickers, moves)
    plt.title("Top Movers (1D %)")
    plt.xlabel("Ticker")
    plt.ylabel("% Move")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(p, dpi=160)
    plt.close()
    return p