<template>
  <div class="main-container" ref="mainContainer">
    <div
      v-show="!rightFullScreen"
      class="box bg-image_view ml-1 my-1 mt-2 rounded"
      ref="left_container"
      @dblclick.stop="togglePanelActive('left', $event)"
    >
      <LeftPanel :panel-width="leftPanelWidth" />
    </div>
    <div class="d-flex justify-center align-center" ref="splitBar">
      <div
        v-show="!leftFullScreen && !rightFullScreen"
        class="split-bar bg-split-line rounded-lg guide-main-split-bar"
      ></div>
    </div>

    <div
      v-show="!leftFullScreen"
      class="box box_right bg-image_view mr-1 my-1 mt-2 rounded"
      ref="right_container"
      @dblclick.stop="togglePanelActive('right', $event)"
    >
      <RightPanel :panel-width="rightPanelWidth" />
    </div>
  </div>
</template>

<script lang="ts" setup>
import LeftPanel from "./components/left-panel-core/left.vue";
import RightPanel from "./components/right-panel-core/right.vue";
import { ref, onMounted } from "vue";
import emitter from "@/plugins/bus";
import { throttle } from "./components/tools";

const mainContainer = ref<HTMLDivElement>();
const splitBar = ref<HTMLDivElement>();

const left_container = ref<HTMLDivElement>();
const right_container = ref<HTMLDivElement>();
let leftFullScreen = ref(false);
let rightFullScreen = ref(false);
const ignoreElements = ["INPUT", "I", "svg", "path"];
const leftPanelWidth = ref(1000);
const rightPanelWidth = ref(600);

let isDragging = false;
let nav_sticky = false;
onMounted(() => {
  manageEmitters();

  splitBar.value?.addEventListener("mousedown", function (e) {
    isDragging = true;
    document.addEventListener("mousemove", throttle(moveSplitLine, 100));
  });

  document.addEventListener("mouseup", function (e) {
    isDragging = false;
    document.removeEventListener("mousemove", moveSplitLine);
  });
});

function manageEmitters() {
  emitter.on("set_nav_sticky_mode", (val) => {
    nav_sticky = val as boolean;
    if (val && left_container.value?.classList.contains("panel_active")) {
      left_container.value?.classList.add("nav_panel_active");
    } else if (
      val &&
      right_container.value?.classList.contains("panel_active")
    ) {
      right_container.value?.classList.add("nav_panel_active");
    } else {
      left_container.value?.classList.remove("nav_panel_active");
      right_container.value?.classList.remove("nav_panel_active");
    }
  });
}

function moveSplitLine(e: MouseEvent) {
  if (isDragging) {
    const containerRect = (
      mainContainer.value as HTMLDivElement
    ).getBoundingClientRect();
    let clientX = e.clientX;
    if (nav_sticky) {
      clientX = e.clientX + 350;
    }
    const mousePosition = clientX - containerRect.left;

    const minLeft = containerRect.left;
    const maxLeft =
      containerRect.right - (splitBar.value as HTMLDivElement).offsetWidth;
    let percent = ((mousePosition - minLeft) / (maxLeft - minLeft)) * 100;
    // if (percent < 0 || percent > 100) {
    //   return;
    // }
    if (percent < 10) {
      percent = 1;
      (mainContainer.value as HTMLDivElement).style.gridTemplateColumns =
        percent - 1 + "% 1%" + (100 - percent) + "%";
    } else if (percent > 90) {
      percent = 100;
      (mainContainer.value as HTMLDivElement).style.gridTemplateColumns =
        percent - 1 + "% 1%" + (100 - percent) + "%";
    } else {
      (mainContainer.value as HTMLDivElement).style.gridTemplateColumns =
        percent - 1 + "% 1%" + (100 - percent) + "%";
    }

    leftPanelWidth.value = left_container.value?.getBoundingClientRect()
      .width as number;
    rightPanelWidth.value = right_container.value?.getBoundingClientRect()
      .width as number;
  }
}

function togglePanelActive(panel: string, e: MouseEvent) {
  const nodeName = (e.target as HTMLElement).nodeName;
  if (ignoreElements.includes(nodeName)) return;
  switch (panel) {
    case "left":
      leftFullScreen.value = !leftFullScreen.value;

      left_container.value?.classList.toggle("panel_active");
      if (!left_container.value?.classList.contains("panel_active")) {
        left_container.value?.classList.remove("nav_panel_active");
      } else {
        if (
          nav_sticky &&
          !left_container.value?.classList.contains("nav_panel_active")
        ) {
          left_container.value?.classList.add("nav_panel_active");
        }
      }
      leftPanelWidth.value = left_container.value?.getBoundingClientRect()
        .width as number;
      emitter.emit("resize-left-right-panels", {
        effectPanelSize: leftPanelWidth.value,
        panel: "left",
      });
      emitter.emit("resize-left-right-panels", {
        effectPanelSize: rightPanelWidth.value,
        panel: "right",
      });
      break;
    case "right":
      rightFullScreen.value = !rightFullScreen.value;
      right_container.value?.classList.toggle("panel_active");
      if (!right_container.value?.classList.contains("panel_active")) {
        right_container.value?.classList.remove("nav_panel_active");
      } else {
        if (
          nav_sticky &&
          !right_container.value?.classList.contains("nav_panel_active")
        ) {
          right_container.value?.classList.add("nav_panel_active");
        }
      }
      setTimeout(() => {
        // delay 500ms
        // set a time out to make sure after the browser finish render the doms, then we get the correct panel width.
        rightPanelWidth.value = right_container.value?.getBoundingClientRect()
        .width as number;
        emitter.emit("resize-left-right-panels", {
          effectPanelSize: rightPanelWidth.value,
          panel: "right",
        });
      }, 300);
     
      break;
  }
}
</script>

<style scoped>
.main-container {
  display: grid;
  grid-template-columns: 64% 1% 35%;
  width: 100%;
  /* height: 90vh; */
  overflow: hidden;
  position: relative;
  user-select: none;
  -webkit-user-select: none;
}

.box {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
}
.box_right {
  display: flex;
  align-items: center;
  justify-content: center;
}
.panel_active {
  width: 100%;
  position: fixed;
  z-index: 100;
}
.nav_panel_active {
  width: calc(100vw - 350px);
}

.split-bar {
  width: 4px;
  height: 10%;
  cursor: col-resize;
}
</style>
