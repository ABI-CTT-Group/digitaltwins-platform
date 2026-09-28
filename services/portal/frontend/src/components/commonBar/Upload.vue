<template>
  <div v-if="dialog" @click="closeDialog" class="upload_container">
    <el-upload
      :auto-upload="false"
      @change="loaded"
      @remove="removeLoadFile"
      class="upload-demo"
      drag
      action="/"
      multiple
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">
        Drop file here or <em>click to upload</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">Please drag or upload NRRD files!</div>
        <div class="el-upload__tip">
          Ready to Submit: Please click drak area!!!
        </div>
      </template>
    </el-upload>
  </div>
</template>

<script setup lang="ts">
import { UploadFilled } from "@element-plus/icons-vue";
import type { UploadFile } from "element-plus";

type Props = {
  dialog?: boolean;
};

withDefaults(defineProps<Props>(), {
  dialog: false,
});

let files: Array<File> = [];
let urls: Array<string> = [];
let loadedFiles = false;

const emit = defineEmits(["onCloseDialog", "getLoadFilesUrls"]);
const closeDialog = (e: MouseEvent) => {
  let e1 = e.currentTarget;
  let e2 = e.target;
  if (e1 === e2) {
    // openDialog.value = false;
    files.forEach((file) => {
      const url = URL.createObjectURL(file);
      urls.push(url);
    });
    emit("getLoadFilesUrls", urls, "uploadFiles");
    emit("onCloseDialog", false);
    loadedFiles = true;
    resetLoadState();
  }
};

const resetLoadState = () => {
  files = [];
  urls.forEach((url) => {
    URL.revokeObjectURL(url);
  });
  urls = [];
};

const loaded = (uploadFile: UploadFile) => {
  //   console.log(uploadFile);
  //   console.log(uploadFile.name);
  //   console.log(uploadFile.raw);
  if (loadedFiles) {
    loadedFiles = false;
    resetLoadState();
  }

  let filename = uploadFile.name;
  let file: File | undefined;
  if (filename.match(/\.(nrrd)$/)) {
    file = uploadFile.raw as File;
    files.push(file);
  }
  if (!file) {
    onError("No .nrrd asset found!");
  }
};

const removeLoadFile = (uploadFile: UploadFile) => {
  files = files.filter((file) => {
    return file.name !== uploadFile.name;
  });
};

/**
 * @param  {Error} error
 */
const onError = (error: string | Error) => {
  let message = ((error as Error) || {}).message || error.toString();
  if (message.match(/ProgressEvent/)) {
    message =
      "Unable to retrieve this file. Check JS console and browser network tab.";
  } else if (message.match(/Unexpected token/)) {
    message = `Unable to parse file content. Verify that this file is valid. Error: "${message}"`;
  } else if (
    error &&
    (error as any).target &&
    (error as any).target instanceof Image
  ) {
    message = "Missing texture: " + (error as any).target.src.split("/").pop();
  }
  window.alert(message);
};
</script>

<style scoped>
.upload_container {
  position: fixed;
  z-index: 1000;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
}
.upload-demo {
  width: 60vw;
}
</style>
