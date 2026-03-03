from pathlib import Path
from utils.parser import parse_config
from core.pipeline import run_pipeline


def main():
    config_path = Path(__file__).parent / "config.yaml"
    config = parse_config(config_path)
    run_pipeline(config)


if __name__ == "__main__":
    main()
