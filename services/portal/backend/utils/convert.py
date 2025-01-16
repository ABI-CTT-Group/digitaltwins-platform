import numpy as np
import json
import SimpleITK as sitk
from skimage.measure import marching_cubes
import nibabel as nib
from .tools import get_file_path, getMaskData
from .setup import Config, TumourData


def convert_json_to_obj(patient_id):
    """
    convert nii file to obj file
    :param patient_id:
    :return:
    """
    json_source = get_file_path(patient_id, "json", "mask.json")
    dest = get_file_path(patient_id, "obj", "mask.obj")

    if json_source is None:
        print(f"mask.json path is None, Check your manifest.xlsx file's patient_id {patient_id}")
        Config.Updated_Mesh = True
        return
    elif dest is None:
        print(f"mask.obj path is None, Check your manifest.xlsx file's patient_id {patient_id}")
        Config.Updated_Mesh = True
        return

    if Config.MASKS == None:
        if Config.ClearAllMask:
            print("Clear all masks by frontend, So set the  Config.Updated_Mesh to True.")
            Config.Updated_Mesh = True
            return
        else:
            # with open(json_source) as user_file:
            #     file_contents = user_file.read()
            #     parsed_json = json.loads(file_contents)
            #     user_file.close()
            getMaskData(json_source)
            if Config.MASKS["hasData"] == False:
                print("No mask data has been found, So set the  Config.Updated_Mesh to True.")
                Config.Updated_Mesh = True
                return
            parsed_json = Config.MASKS["label1"]
    else:
        parsed_json = Config.MASKS["label1"]

    images = []
    width = parsed_json[0]["width"]
    height = parsed_json[0]["height"]
    depth = len(parsed_json)
    for i in range(depth):
        data = parsed_json[i]["data"]
        if len(data) == 0:
            data = [0] * width * height * 4
        images.append(data)
    pixels = np.array(images, dtype=np.uint8).reshape((depth, height, width, 4))

    # Take the average of the RGB values and use the Alpha value as the transparency
    merged_pixels = np.mean(pixels[:, :, :, :3], axis=3)
    merged_pixels[merged_pixels > 0] = 255
    arr = np.transpose(merged_pixels, (2, 1, 0))
    spacing = parsed_json[0]["voxelSpacing"]
    origin = parsed_json[0]["spaceOrigin"]
    count = np.count_nonzero(arr > 0)
    TumourData.volume = count * spacing[0] * spacing[1] * spacing[2]
    Config.MASKS['volume'] = TumourData.volume
    try:
        verts, faces, normals, values = marching_cubes(arr)
        # voxel grid coordinates to world coordinates: verts * voxel_size + origin
        verts = verts * spacing + origin
        # without spacing
        # verts = verts + img.affine[0:3, -1]

        faces = faces + 1

        for idx, normal in enumerate(normals):
            normal = [-n for n in normal]
            normals[idx] = normal

        with open(dest, 'w') as out_file:
            for item in verts:
                out_file.write("v {0} {1} {2}\n".format(item[0], item[1], item[2]))
            for item in normals:
                out_file.write("vn {0} {1} {2}\n".format(item[0], item[1], item[2]))
            for item in faces:
                out_file.write("f {0}//{0} {1}//{1} {2}//{2}\n".format(item[0], item[1], item[2]))

            print("finish write obj")
        out_file.close()
        # tell websocket the mesh is ready send to frontend
        print("Finish convert mask to obj, So set the  Config.Updated_Mesh to True.")
        Config.Updated_Mesh = True

    except RuntimeError as e:
        try:
            dest.unlink()
            TumourData.volume = 0
            Config.Updated_Mesh = True
            print(f"{dest.name} file delete successfully!")
        except OSError as e:
            print(f"fail to delete file!")


def convert_to_nii(patient_id):
    """
    convert pixels to nii file
    :param patient_id: case name
    :return:
    """
    print("start converting...")
    nrrd_path = get_file_path(patient_id, "nrrd", "contrast_0.nrrd")
    if nrrd_path is None:
        nrrd_path = get_file_path(patient_id, "nrrd", "c0.nrrd")
    mask_path = get_file_path(patient_id, "json", "mask.json")
    nii_path = get_file_path(patient_id, "nii.gz", "mask.nii.gz")
    nii_path_2 = get_file_path(patient_id, "nii.gz", "mask_2.nii.gz")
    nii_path_3 = get_file_path(patient_id, "nii.gz", "mask_3.nii.gz")


    if nrrd_path is None:
        print("contrast_0.nrrd path is None")
        return
    elif mask_path is None:
        print("mask.json path is None")
        return
    elif nii_path is None:
        print("mask.nii.gz path is None")
        return

    origin_nrrd_image = sitk.ReadImage(nrrd_path)
    headerKeys = origin_nrrd_image.GetMetaDataKeys()

    with open(mask_path) as user_file:
        file_contents = user_file.read()
        parsed_json_mask = json.loads(file_contents)
    parsed_json = parsed_json_mask["label1"]
    parsed_json_2 = parsed_json_mask["label2"]
    parsed_json_3 = parsed_json_mask["label3"]
    for file_index in range(3):
        # Save the image as a NIfTI file
        if file_index == 0:
            convert_core(parsed_json, nii_path, headerKeys, origin_nrrd_image)
        # elif file_index == 1:
        #     convert_core(parsed_json_2, nii_path_2, headerKeys, origin_nrrd_image)
        # elif file_index == 2:
        #     convert_core(parsed_json_3, nii_path_3, headerKeys, origin_nrrd_image)


def convert_core(parsed_json, nii_path, headerKeys, origin_nrrd_image):
    images = []
    width = parsed_json[0]["width"]
    height = parsed_json[0]["height"]
    depth = len(parsed_json)
    for i in range(len(parsed_json)):
        data = parsed_json[i]["data"]
        if len(data) == 0:
            data = [0] * width * height * 4
        images.append(data)
    try:
        pixels = np.array(images, dtype=np.uint8).reshape((depth, height, width, 4))
        # Take the average of the RGB values and use the Alpha value as the transparency
        merged_pixels = np.mean(pixels[:, :, :, :3], axis=3)
        # print(np.amax(merged_pixels))
        merged_pixels[merged_pixels > 50] = 255

        print(merged_pixels.shape)

        nii_image = sitk.GetImageFromArray(merged_pixels)
        for key in headerKeys:
            nii_image.SetMetaData(key, origin_nrrd_image.GetMetaData(key))
        spacing = parsed_json[0]["voxelSpacing"]
        origin = parsed_json[0]["spaceOrigin"]
        nii_image.SetSpacing(spacing)
        nii_image.SetOrigin(origin)

        sitk.WriteImage(nii_image, nii_path)
        img = nib.load(nii_path)
        img.affine[0:3, -1] = origin
        nib.save(img, nii_path)
        print("convert successfully!")
    except Exception as e:
        print("An error occurred: ", e)
        import traceback
        print(traceback.format_exc())


def convert_to_obj(patient_id):
    """
    convert nii file to obj file
    :param patient_id:
    :return:
    """
    source = get_file_path(patient_id, "nii.gz", "mask.nii.gz")
    dest = get_file_path(patient_id, "obj", "mask.obj")

    img = nib.load(source)
    spacing = img.header.get_zooms()
    arr = img.get_fdata()
    try:
        verts, faces, normals, values = marching_cubes(arr)
        # voxel grid coordinates to world coordinates: verts * voxel_size + origin
        verts = verts * spacing + img.affine[0:3, -1]
        # without spacing
        # verts = verts + img.affine[0:3, -1]

        faces = faces + 1

        for idx, normal in enumerate(normals):
            normal = [-n for n in normal]
            normals[idx] = normal

        with open(dest, 'w') as out_file:
            for item in verts:
                out_file.write("v {0} {1} {2}\n".format(item[0], item[1], item[2]))
            for item in normals:
                out_file.write("vn {0} {1} {2}\n".format(item[0], item[1], item[2]))
            for item in faces:
                out_file.write("f {0}//{0} {1}//{1} {2}//{2}\n".format(item[0], item[1], item[2]))
        out_file.close()
    except RuntimeError as e:
        try:
            dest.unlink()
            print(f"{dest.name} file delete successfully!")
        except OSError as e:
            print(f"fail to delete file!")


def convert_to_nii_sigel_channel(patient_id):
    nii_image = convert_json_data(patient_id)
    nii_path = get_file_path(patient_id, "nii.gz", "mask.nii.gz")
    # Save the image as a NIfTI file
    sitk.WriteImage(nii_image, nii_path)
    print("convert successfully!")


def convert_to_nrrd_sigel_channel(patient_id):
    nrrd_image = convert_json_data(patient_id)
    nrrd_path = get_file_path(patient_id, "nrrd", "mask.nrrd")
    # Save the image as a NRRD file
    sitk.WriteImage(nrrd_image, nrrd_path)
    print("convert successfully!")


def convert_json_data(patient_id):
    print("start converting...")

    nrrd_path = get_file_path(patient_id, "nrrd", "contrast_0.nrrd")
    mask_path = get_file_path(patient_id, "json", "mask.json")

    nrrd_image = sitk.ReadImage(nrrd_path)
    headerKeys = nrrd_image.GetMetaDataKeys()

    with open(mask_path) as user_file:
        file_contents = user_file.read()
        parsed_json_mask = json.loads(file_contents)
    images = []
    parsed_json = parsed_json_mask["label1"]
    width = parsed_json[0]["width"]
    height = parsed_json[0]["height"]
    depth = len(parsed_json)
    for i in range(len(parsed_json)):
        data = parsed_json[i]["data"]
        if len(data) == 0:
            data = [0] * width * height * 4
        images.append(data)

    try:
        pixels = np.array(images, dtype=np.uint8).reshape((depth, height, width, 4))

        # Take the average of the RGB values and use the Alpha value as the transparency
        # merged_pixels = np.mean(pixels[:, :, :, :3], axis=3)
        merged_pixels = pixels[:, :, :, 0] + pixels[:, :, :, 1] + pixels[:, :, :, 2] + pixels[:, :, :, 3]
        merged_pixels[merged_pixels > 0] = 255

        new_image = sitk.GetImageFromArray(merged_pixels)

        new_image.CopyInformation(nrrd_image)
        spacing = parsed_json[0]["voxelSpacing"]
        origin = parsed_json[0]["spaceOrigin"]
        new_image.SetSpacing(spacing)
        new_image.SetOrigin(origin)
        #
        # for key in headerKeys:
        #     new_image.SetMetaData(key, nrrd_image.GetMetaData(key))

        return new_image

    except Exception as e:
        print("An error occurred: ", e)
        import traceback
        print(traceback.format_exc())


def convert_to_nii_full_channels(patient_id):
    print("start converting...")
    mask_path = get_file_path(patient_id, "json", "mask.json")

    with open(mask_path) as user_file:
        file_contents = user_file.read()
        parsed_json = json.loads(file_contents)
    images = []
    width = parsed_json[0]["width"]
    height = parsed_json[0]["height"]
    for i in range(len(parsed_json)):
        data = parsed_json[i]["data"]
        if len(data) == 0:
            data = [0] * width * height * 4
        images.append(data)

    spacing = parsed_json[0]["voxelSpacing"]
    origin = parsed_json[0]["spaceOrigin"]
    try:
        rgba_pixels = np.array(images, dtype=np.uint8)  # Convert pixel data to a numpy array of uint8 type
        rgba_pixels = rgba_pixels.reshape((-1, 4))  # Reshape the pixel data to have 4 columns

        rgb_pixels = rgba_pixels[:, :-1]

        rgb_image = np.array(rgb_pixels, dtype=np.float32).reshape((len(parsed_json), height, width, 3))

        # Convert the RGB image to a grayscale image
        red_channel = sitk.VectorIndexSelectionCast(sitk.GetImageFromArray(rgb_image), 0)
        green_channel = sitk.VectorIndexSelectionCast(sitk.GetImageFromArray(rgb_image), 1)
        blue_channel = sitk.VectorIndexSelectionCast(sitk.GetImageFromArray(rgb_image), 2)
        nii = sitk.Compose(red_channel, green_channel, blue_channel)

        nii.SetSpacing(spacing)
        nii.SetOrigin(origin)

        nii_path = get_file_path(patient_id, "nii.gz", "mask.nii.gz")
        # Save the image as a NIfTI file
        sitk.WriteImage(nii, nii_path)
        print("convert successfully!")

    except Exception as e:
        print("An error occurred: ", e)
        import traceback
        print(traceback.format_exc())
