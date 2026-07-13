import argparse
import json
import sys
from pathlib import Path

from parse_knowledge_markdown import extract_scene_overview, split_md_records, split_workflow_records


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("docs_directory")
    args = parser.parse_args()
    output = {"rules": [], "workflows": [], "scene_overviews": []}

    for path in sorted(Path(args.docs_directory).glob("*.md")):
        content = path.read_text(encoding="utf-8")
        output["scene_overviews"].append(extract_scene_overview(content, path.name))
        output["rules"].extend(split_md_records(content, path.name))
        output["workflows"].extend(split_workflow_records(content, path.name))

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
