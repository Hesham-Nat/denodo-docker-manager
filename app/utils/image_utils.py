import os

def parse_docker_image_file_for_denodo(file_path="data/denodo_docker_images.txt"):
    image_tags = []

    if not os.path.exists(file_path):
        return []

    with open(file_path, "r") as f:
        lines = f.readlines()[1:]  # Skip header

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        tags = parts[1].split(',')
        filtered_tags = [tag for tag in tags if not tag.startswith("sha256")]
        image_tags.extend(filtered_tags)
    sorted_tags = sorted(image_tags)
    reversed_tags = list(reversed(sorted_tags))
    return reversed_tags

def parse_docker_image_file_for_sm(file_path="data/sm_docker_images.txt"):
    image_tags = []

    if not os.path.exists(file_path):
        return []

    with open(file_path, "r") as f:
        lines = f.readlines()[1:]  # Skip header

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        tags = parts[1].split(',')
        filtered_tags = [tag for tag in tags if not tag.startswith("sha256")]
        image_tags.extend(filtered_tags)
    sorted_tags = sorted(image_tags)
    reversed_tags = list(reversed(sorted_tags))
    return reversed_tags

