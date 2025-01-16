<template>
    <v-card class="right-value-panel mt-2 guide-right-value-panel" color="right-display-panel">
        <div color="primary">
            <span>Tumour volume:</span> <span>{{ tumourVolume }} cm<sup>3</sup></span>
        </div>
        <div>
            <span>Tumour extent:</span> <span>{{ tumourExtent }} mm</span>
        </div>
        <div class="skin">
            <span>Skin:</span> <span>{{ skinDist }} mm</span>
        </div>
        <div class="ribcage">
            <span>Ribcage:</span> <span>{{ ribDist }} mm</span>
        </div>
        <div class="nipple">
            <span>Nipple:</span> <span>{{ nippleDist }} mm</span>
        </div>
        <div class="nipple">
            <span></span> <span>{{ nippleClock }}</span>
        </div>
    </v-card>
</template>

<script setup lang="ts">

defineProps({
    tumourVolume: Number,
    tumourExtent: Number,
    skinDist: String,
    ribDist: String,
    nippleDist: String,
    nippleClock: String
})
</script>

<style scoped>
.right-value-panel {
  position: absolute;
  left: 0px;
  top: 0px;
  width: 200px;
  height: 150px;
  background-color: rgba(255, 255, 255, 0.1);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 10px;
  padding: 10px 15px;
  font-size: smaller;
  user-select: none;
  -webkit-user-select: none;
  /* display: flex; */
  /* align-items: center; */
  /* justify-content: center; */
}

.right-value-panel > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.skin {
  color: #FFEB3B;
}
.ribcage {
  color: darkcyan;
}
.nipple {
  color: hotpink;
}
</style>