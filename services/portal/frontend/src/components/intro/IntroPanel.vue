<template>
  <v-menu transition="scroll-x-reverse-transition" >
    <template v-slot:activator="{ props }">
      <v-btn
        color="info"
        class="ma-2"
        density="compact"
        icon="mdi-information-outline"
        v-bind="props"
      >
      </v-btn>
    </template>
    <v-sheet
      border="md"
      class="pa-6 text-white mx-auto"
      color="surface"
      max-width="550"
      max-height="750"
    >
      <h4 class="text-h5 font-weight-bold mb-4">How to use:</h4>

      <p class="mb-8">
        <a href="#" class="text-red-accent-2 text-decoration-none">Full panel view: </a>
        <p class="ml-9">Mouse left double click the panel.</p>

        <a href="#" class="text-red-accent-2 text-decoration-none">Zoom: </a>
        <p class="ml-9">Scroll mouse wheel.</p>

        <a href="#" class="text-red-accent-2 text-decoration-none">Pan: </a>
         <p class="ml-9">Mouse right click <a href="#" class="text-teal text-decoration-none">+</a> drag image.</p>

        <a href="#" class="text-red-accent-2 text-decoration-none"
          >Switch slice:
        </a>
         <p class="ml-9">Mouse left click <a href="#" class="text-teal text-decoration-none">+</a> drag image.</p>

        <a href="#" class="text-red-accent-2 text-decoration-none"
          >Painting:
        </a>
         <p class="ml-9">Press <a href="#" class="text-teal text-decoration-none font-weight-bold">shift</a> key on your keyboard ( <a href="#" class="text-warning text-decoration-none font-weight-bold">Don't release it</a> ), then use mouse
        left click to paint.</p>

        <a href="#" class="text-red-accent-2 text-decoration-none">Undo: </a>
         <p class="ml-9">&#9734; In GUI click undo; or </p>
         <p class="ml-9">&#9734; On keyborad using ctrl <a href="#" class="text-teal text-decoration-none">+</a> z (Windows) /
        command <a href="#" class="text-teal text-decoration-none">+</a> z (Mac).</p>

        <a href="#" class="text-red-accent-2 text-decoration-none"
          >Cursor Inspector:
        </a>
         <p class="ml-9">Press <a href="#" class="text-teal text-decoration-none font-weight-bold">s</a> key on the keyboard ( <a href="#" class="text-warning text-decoration-none font-weight-bold">Once</a> ) to enable/disable, then left click on images,
        and use bottom tool's bar to switch the image orientation.</p>
      </p>

      

      <v-btn
        block
        class="text-none text-black mb-4"
        color="teal-accent-3"
        variant="flat"
        @click="guideTour"
      >
        Guide Tour
      </v-btn>
      <v-btn
        block
        class="text-none text-black mb-4"
        color="red-accent-2"
        size="x-large"
        variant="flat"
      >
        Got it
      </v-btn>
    </v-sheet>
  </v-menu>
</template>

<script setup lang="ts">
import introJs from 'intro.js';
import { useTheme } from "vuetify";
import emitter from "@/plugins/bus";

const theme = useTheme();
let tipclass = '';
let helperclass = '';

function guideTour() {

  if(theme.global.current.value.dark){
    tipclass = "tipText-dark";
    helperclass = 'helperLayer-dark';
  }else{
    tipclass = "tipText";
    helperclass = 'helperLayer';
  }

  emitter.emit("guide_status", "start");

  setTimeout(()=>{
    introJs().setOptions({
        // prevLabel: "prev",
        // nextLabel: "next",
        // skipLabel: "Jump",
        // doneLabel: "Finish"
        tooltipClass: tipclass,
        highlightClass: helperclass,
        steps:[
          {
            title: 'Welcome',
            intro: 'Tumour Position & Extent Reporting Guide Tour! 👋'
          },
          {
            element: document.querySelector('.guide-bar-nav'),
            intro: "Click here to expand/hide the 'Tools Core Settings'",
          },
          {
            element: document.querySelector('.guide-expand-panel'),
            intro: "Discover more in Tools Core Settings, all APP's configs you can find in here!",
          },
          {
            title: "Core Case Image Control",
            element: document.querySelector('.guide-cases-overall'),
            intro: "Choose Your Images and Contrasts here.",
          },
          {
            title: "Register / Origin MRI",
            element: document.querySelector('.guide-case-switch'),
            intro: "Use Switch Button to show origin or Register MRI.",
          },
          {
            title: "Draw Panel Settings",
            element: document.querySelector('.guide-operation-overall'),
            intro: "Click buttons to setup the draw panel configurations.",
            position: 'right',
          },

          {
            title: "Draw Panel Settings",
            element: document.querySelector('.guide-operation-functional-control'),
            intro: `To use the Pencil, Brush, or Eraser, press and hold the Shift key, then click and drag with the left mouse button to draw.
The Sphere tool allows you to mark the tumor without needing to hold the Shift key. Simply click with the left mouse button to select the center of the sphere, and use the mouse wheel to adjust its size when you still hold the left mouse button.`,
            position: 'right',
          },
          {
            title: "Draw Panel Settings",
            element: document.querySelector('.guide-operation-slider-control'),
            intro: `Choose function buttons and drag slider to change draw panel or MRI settings (Also you can use window mode, press 'ctrl' key once to enable,
                    then use left mouse drag horizontally to change the WindowHigh, and drag vertically to change the WindowCenter. At last, press 'ctrl' key again back to normal mode),
                    Opacity is for mask's opacity in draw panel, B&E Size is for controlling the 
                    Brush and Eraser size. Others are controllers for MRI's contrast.`,
            position: 'right',
          },
          {
            title: "Draw Panel Settings",
            element: document.querySelector('.guide-operation-comm-btns'),
            intro: `Functional buttons: Undo:undo last operation -> Ctrl + z, 
                    Reset ZOOM: reset MRI size to origin size, CLEAR SLICE MASK: 
                    clear mask on current slice, CLEAR ALL SLICES MASKS: clear all masks under this case.`,
            position: 'right',
          },

          {
            title: "Left Draw Panel",
            element: document.querySelector('.guide-left-panel'),
            intro: `Display MRIs, allow users to draw masks on MRI, Double-Click to expand the panel.`,
          },
          {
            title: "Left Panel Controller",
            element: document.querySelector('.guide-left-nav-tool'),
            intro: "Function controls for Left Panel.",
          },
          {
            title: "Left Panel Controller",
            element: document.querySelector('.guide-left-slider'),
            intro: "Slice slider: drag to switch MRI slice.",
          },

          {
            title: "Left Panel Controller",
            element: document.querySelector('.guide-left-views'),
            intro: "Switch MRI to Sagittal / Axial / Coronal views, you can press `s` key once on keyboard and left click on MRI to achieve precision positioning.",
          },
          {
            title: "Left Panel Controller",
            element: document.querySelector('.guide-left-sync'),
            intro: "Sync masks to 3D model in right 3D panel.",
          },
          {
            title: "Split Bar",
            element: document.querySelector('.guide-main-split-bar'),
            intro: "Drag it to control panels size.",
          },
          {
            title: "Right 3D Panel",
            element: document.querySelector('.guide-right-panel'),
            intro: "Display 3D models.",
          },
          {
            title: "Value Set Area",
            element: document.querySelector('.guide-right-value-panel'),
            intro: "Display Tumour Informations.",
          },

          {
            title: "Right 3D Panel Controller",
            element: document.querySelector('.guide-right-nav-tool'),
            intro: "Function controls for Right Panel.",
          },
          {
            title: "3D MRI views",
            element: document.querySelector('.guide-right-twoD-view'),
            intro: `Sagittal / Axial / Coronal Views:
After clicking once, a slider will appear on the left to control the slice index. You can also drag the mouse left-click to switch slices. Use the middle mouse button to rotate, scroll the middle wheel to zoom, and right-click to pan. Double-click to switch the image to a front view.`,
          },
          {
            title: "Back to 3D view",
            element: document.querySelector('.guide-right-threeD-view'),
            intro: `Click 3D view button, will not change the slice index and image position in 3D. 
                    Click reset view, will change the slice index and image position to initial status.
                    Then use mouse left click to Rotate, scroll middle wheel for Zoom, right click for Pan.`,
          },
          {
            title: "Guide Tour Finished",
            intro: "Enjoy your journey on Tumour Position & Extent Reporting APP! 🙌",
          },
        ]
    }).oncomplete(function () {
        //after jump clicked
    }).onexit(function () {
        //after exit clicked
    }).onchange(function(targetElement:HTMLDivElement) {
      if(!!targetElement){
        var dataToolValue = targetElement.getAttribute("data-tool");
        if(dataToolValue === "expandtool"){
          emitter.emit("guide_to_drawer_status", "open");
        }else if(dataToolValue === "operationtool"){
          emitter.emit("guide_to_operation_status", "open");
        }
      }
    }).start();
  }, 500);
}

</script>

<style>
.tipText{
  background-color: #ffffff;
  box-shadow: 0 3px 30px rgba(211, 209, 209, 0.3);
}
.helperLayer{
  /* z-index: -1 !important; */
  box-shadow: #009688 0px 0px 1px 2px, rgba(33, 33, 33, 0.5) 0px 0px 0px 5000px !important;
}
.tipText-dark{
  background-color: #656464;
  box-shadow: 0 3px 30px rgb(226 217 217 / 30%);
}
.helperLayer-dark{
  /* z-index: -1 !important; */
  box-shadow: rgb(222 89 89 / 80%) 0px 0px 1px 2px, rgba(33, 33, 33, 0.5) 0px 0px 0px 5000px !important;
}

</style>
