
import os
import pandas as pd
import numpy as np
import cesarp.common
import multiprocessing as mp


def read_and_reshape_csv(file_path):
    max_columns = 9
    # Read the CSV file into a DataFrame
    df = pd.read_csv(file_path,header=None)

    # Determine the current number of columns
    current_columns = df.shape[1]

    # If the DataFrame has fewer columns than max_columns, pad with NaN
    if current_columns < max_columns:
        # Pad the DataFrame with NaN values to ensure it has max_columns
        padding = pd.DataFrame(-999, index=np.arange(len(df)), columns=np.arange(current_columns, max_columns))
        df = pd.concat([df, padding], axis=1)

    # Reshape the DataFrame to a 3D tensor with shape (24, 365, max_columns)
    reshaped_array = df.to_numpy().reshape(365, 24, max_columns)

    return reshaped_array


def concatenate_tensors(tensors):
    # Concatenate all tensors along a new fourth dimension
    return np.stack(tensors, axis=-1)

def __abs_path(path):
    return cesarp.common.abs_path(path, os.path.abspath(__file__))

import multiprocessing as mp

# Function to read, reshape, and return the tensor
def process_file(path):
    reshaped_tensor = read_and_reshape_csv(path)
    return reshaped_tensor

if __name__ == '__main__':
    # List to store data frames
    file_paths = []

    for i in range(10001, 20001):  # 99856 (1,10001) (10001,20001)
        file_name = __abs_path(f"./results/example/EPF_inputs/fid_{i}.csv")
        file_paths.append(file_name)

    # List to store the resulting tensors
    tensors = []

    # Use multiprocessing.Pool to parallelize the process
    with mp.Pool() as pool:
        # Map the file paths to the process_file function in parallel
        results = pool.map(process_file, file_paths)

        # Extend the tensors list with the results
        tensors.extend(results)

    # List of file paths for CSVs
    # file_paths = ['path_to_file1.csv', 'path_to_file2.csv', 'path_to_filem.csv']

    # Determine the maximum number of columns in any file
    # max_columns = 9  # max(pd.read_csv(f, nrows=0).shape[1] for f in file_paths)

    # List to hold each reshaped tensor
    # tensors = []

    # for path in file_paths:
    #     reshaped_tensor = read_and_reshape_csv(path)
    #     tensors.append(reshaped_tensor)

    # Concatenate all reshaped tensors
    final_tensor = concatenate_tensors(tensors)

    # Save the final tensor to a binary file using numpy
    # save_path = __abs_path(f"./results/example/final_tensor.npy")
    save_path = __abs_path(f"./results/example/final_tensor_test.npy")
    np.save(save_path, final_tensor)

    print("Tensor saved successfully with shape:", final_tensor.shape)