# coding=utf-8

import random
import pandas as pd
from shapely.geometry import box
from shapely.affinity import rotate, translate


def generate_centered_buildings_in_grid(grid_root, block_size, min_building_size, max_building_size,
                                        min_building_height, max_building_height):
    """

    :param grid_root: square root of the desired number of buildings
    :param block_size: desired block width/length
    :param min_building_size: desired minimum building width/length
    :param max_building_size: desired maximum building width/length
    :param min_building_height: desired minimum building height
    :param max_building_height: desired maximum building height
    """
    building_data = []

    for i in range(grid_root):
        for j in range(grid_root):
            # Calculate the center of the block
            center_x = (i * block_size) + (block_size / 2)
            center_y = (j * block_size) + (block_size / 2)

            # Determine building dimensions and orientation
            width = random.uniform(min_building_size, max_building_size)
            depth = random.uniform(min_building_size, max_building_size)
            angle = random.uniform(0, 360)  # rotation angle in degrees
            height = random.uniform(min_building_height, max_building_height)  # height of each building

            # Create a rectangle centered at the origin, rotate, and then translate it to the block center
            rect = box(-width / 2, -depth / 2, width / 2, depth / 2)
            rotated_rect = rotate(rect, angle, origin='center', use_radians=False)
            final_rect = translate(rotated_rect, xoff=center_x, yoff=center_y)

            # Store the vertices in the list, including closing the loop by repeating the first vertex at the end
            vertices = list(final_rect.exterior.coords)
            for vx, vy in vertices:
                building_data.append({
                    "TARGET_FID": i * grid_root + j + 1,
                    "POINT_X": vx,
                    "POINT_Y": vy,
                    "HEIGHT": height
                })

    # Create DataFrame from list
    vertices_df = pd.DataFrame(building_data, columns=["TARGET_FID", "POINT_X", "POINT_Y", "HEIGHT"])
    vertices_df.to_csv('data/Random_SiteVertices.csv', index=False)
