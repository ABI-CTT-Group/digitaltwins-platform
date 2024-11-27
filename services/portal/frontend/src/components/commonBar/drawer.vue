<template>
  <div class="wrap" ref="container" id="right_drawer">
    <div class="nav">
      <div class="menu">
        <div
          v-for="item in viewData"
          class="item"
          @click.stop="onSigleClick(item.label)"
          @dblclick.stop="onDoubleClick(item.label)"
        >
          <div class="light"></div>
          <div class="licon">
            <span class="iconfont"><img :src="item.img" alt="" /></span>
          </div>
          <div class="con">{{ item.name }}</div>
          <!-- <div class="ricon"></div> -->
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import sagittalImg from "@/assets/images/person_left_view_white.png";
import axialImg from "@/assets/images/person_top_down_white.png";
import coronalImg from "@/assets/images/person_anterior_white.png";
import clockImg from "@/assets/images/clock_white.png";
import resetImg from "@/assets/images/reset.png";

const viewData = [
  {
    name: "Sagittal view",
    label: "sagittal",
    img: sagittalImg,
  },
  {
    name: "Axial view",
    label: "axial",
    img: axialImg,
  },
  {
    name: "Coronal view",
    label: "coronal",
    img: coronalImg,
  },
  // {
  // name:"Clock function",
  // label:"clock",
  // img:clockImg
  // },
  {
    name: "Reset views",
    label: "reset",
    img: resetImg,
  },
];

const container = ref<HTMLElement>();
const emit = defineEmits(["onViewSingleClick", "onViewDoubleClick"]);

const onSigleClick = (view: string) => {
  emit("onViewSingleClick", view);
};

const onDoubleClick = (view: string) => {
  emit("onViewDoubleClick", view);
};

onMounted(() => {
  const containerDiv = container.value as HTMLDivElement;
});
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  color: rgba(255, 255, 255, 1);
}

.wrap {
  width: 250px;
  height: 90px;
  position: fixed;
  right: -170px;

  display: flex;
  align-items: center;
  justify-content: center;
  transition: 0.5s;
  z-index: 199;
}
.nav {
  position: absolute;
  left: 0;
  width: 80px;
  /* width: 280px; */
  max-height: 90vh;
  background: rgba(0, 0, 0, 0.8);
  border-radius: 20px;
  overflow: hidden;
  transition: 0.5s;
}
.nav:hover {
  width: 250px;
}
.wrap:hover {
  right: 0;
}

.btn {
  width: 60px;
  height: 10px;
  display: flex;
  justify-content: space-around;
  margin-left: 25px;
  margin-top: 25px;
}
.btn-item {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.btn-item:nth-child(1) {
  background-color: #eb5a56;
}
.btn-item:nth-child(2) {
  background-color: #f8bc33;
}
.btn-item:nth-child(3) {
  background-color: #62cb44;
}
.icon {
  width: 250px;
  height: 60px;
  margin-left: 25px;
  margin-top: 20px;
  display: flex;
}
.icon-img {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  border: 4px solid rgba(255, 255, 255, 0.3);
  overflow: hidden;
}
.icon-img img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}
.icon-con {
  height: 60px;
  margin-left: 25px;
}
.icon-con p {
  padding-top: 5px;
}
.icon-con h2 {
  font-weight: 400;
}
.line {
  width: 60px;
  height: 1px;
  background: rgba(245, 253, 255, 0.5);
  margin: 20px 25px;
  transition: 0.5s;
}
.nav:hover .line {
  width: 230px;
}
.title {
  width: 60px;
  margin-left: 25px;
  margin-bottom: 20px;
}
.title p {
  font-size: 14px;
}
.menu {
  width: 200px;
  margin-left: 25px;
}
.item {
  display: flex;
  position: relative;
  transition: 0.5s;
  border-radius: 6px;
}
.item:hover {
  background: rgba(255, 255, 255, 0.1);
  cursor: pointer;
}
.licon {
  /* width: 60px; */
  height: 50px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.con {
  width: 0;
  height: 50px;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: 0.5s;
  overflow: hidden;
  position: relative;
  left: 5px;
  opacity: 0;
}
.nav:hover .con {
  width: 160px;
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 1;
}
.ricon {
  width: 0;
  height: 50px;
  transition: 0.5s;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  opacity: 0;
}
.nav:hover .ricon {
  width: 60px;
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 1;
}
.iconfont {
  font-size: 26px;
}
.iconfont img {
  width: 26px;
  height: 26px;
}
.ricon iconfont {
  font-size: 20px;
  color: #62cb44;
}
.light {
  width: 6px;
  height: 50px;
  background: #eb5a56;
  position: absolute;
  left: -25px;
  transition: 0.5s;
  border-top-right-radius: 4px;
  border-bottom-right-radius: 4px;
  opacity: 0;
}
.item:hover .light {
  opacity: 1;
}
.serve {
  width: 60px;
  background: rgba(0, 0, 0, 0.7);
  margin-left: 25px;
  border-radius: 10px;
  overflow: hidden;
  transition: 0.5s;
}

.nav:hover .serve {
  width: 230px;
}
</style>
