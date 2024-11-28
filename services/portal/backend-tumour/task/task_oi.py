from utils import convert_to_nii_sigel_channel, tools,convert, Config
import io

def json_to_nii(casename):
    convert.convert_json_to_obj(casename)
    tools.save()
    # Performing time-consuming calculation tasks
    # convert_to_nii_sigel_channel(casename)
    # convert.convert_to_nrrd_sigel_channel(casename)
    # convert.convert_to_nii_full_channels(casename)
    convert.convert_to_nii(casename)
    # convert.convert_to_obj(casename)
    print("finish covert nii and mesh.")

async def on_complete():
    print("conplete")
    # Config.Updated_Mesh = True
