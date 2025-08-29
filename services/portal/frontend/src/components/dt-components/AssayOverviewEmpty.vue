<template>
  <v-container class="text-center py-16 px-4 no-select assay-overview-empty" fluid>
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <h2 class="title font-weight-bold mb-4 focus-in-expand">
          Oops! It seems this assay is not ready to launch.
        </h2>
        <p class="text-white text-opacity-80 mb-8">
          Please double-check that the workflow, datasets, and cohorts are set up correctly. If the issue continues, kindly reach out to your system administrator for assistance.
        </p>
        <div class="d-flex justify-center flex-wrap gap-4">
            <div class="roll-in-left">
                <v-btn 
                    variant="tonal"
                    class="hover-animate heartbeat"
                    size="80"
                    @click="$router.back()"
                    >
                    <v-icon 
                        icon="mdi-arrow-left" 
                        size="30"
                        color="cyan-darken-2"
                    >
                    </v-icon>
                </v-btn>
            </div>
            
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts" setup>
</script>

<style scoped>
.assay-overview-empty{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}
.title{
    font-size: 3.5rem;
    line-height: 1.2;
}
.text-opacity-80 {
    opacity: 0.8;
}

.gap-4 {
    gap: 1rem;
}
.no-select{
    user-select: none;
    -webkit-user-select: none; /* Safari */
}

.focus-in-expand {
	-webkit-animation: focus-in-expand 0.8s cubic-bezier(0.250, 0.460, 0.450, 0.940) both;
	        animation: focus-in-expand 0.8s cubic-bezier(0.250, 0.460, 0.450, 0.940) both;
}
@-webkit-keyframes focus-in-expand {
  0% {
    letter-spacing: -0.5em;
    -webkit-filter: blur(12px);
            filter: blur(12px);
    opacity: 0;
  }
  100% {
    -webkit-filter: blur(0px);
            filter: blur(0px);
    opacity: 1;
  }
}
@keyframes focus-in-expand {
  0% {
    letter-spacing: -0.5em;
    -webkit-filter: blur(12px);
            filter: blur(12px);
    opacity: 0;
  }
  100% {
    -webkit-filter: blur(0px);
            filter: blur(0px);
    opacity: 1;
  }
}

.roll-in-left {
	-webkit-animation: roll-in-left 1.2s ease-out 0.6s both;
	        animation: roll-in-left 1.2s ease-out 0.6s both;
}

@-webkit-keyframes roll-in-left {
  0% {
    -webkit-transform: translateX(-800px) rotate(-540deg);
            transform: translateX(-800px) rotate(-540deg);
    opacity: 0;
  }
  100% {
    -webkit-transform: translateX(0) rotate(0deg);
            transform: translateX(0) rotate(0deg);
    opacity: 1;
  }
}
@keyframes roll-in-left {
  0% {
    -webkit-transform: translateX(-800px) rotate(-540deg);
            transform: translateX(-800px) rotate(-540deg);
    opacity: 0;
  }
  100% {
    -webkit-transform: translateX(0) rotate(0deg);
            transform: translateX(0) rotate(0deg);
    opacity: 1;
  }
}


.heartbeat {
	-webkit-animation: heartbeat 1.5s ease-in-out 3s infinite both;
	        animation: heartbeat 1.5s ease-in-out 3s infinite both;
}

@-webkit-keyframes heartbeat {
  from {
    -webkit-transform: scale(1);
            transform: scale(1);
    -webkit-transform-origin: center center;
            transform-origin: center center;
    -webkit-animation-timing-function: ease-out;
            animation-timing-function: ease-out;
  }
  10% {
    -webkit-transform: scale(0.91);
            transform: scale(0.91);
    -webkit-animation-timing-function: ease-in;
            animation-timing-function: ease-in;
  }
  17% {
    -webkit-transform: scale(0.98);
            transform: scale(0.98);
    -webkit-animation-timing-function: ease-out;
            animation-timing-function: ease-out;
  }
  33% {
    -webkit-transform: scale(0.87);
            transform: scale(0.87);
    -webkit-animation-timing-function: ease-in;
            animation-timing-function: ease-in;
  }
  45% {
    -webkit-transform: scale(1);
            transform: scale(1);
    -webkit-animation-timing-function: ease-out;
            animation-timing-function: ease-out;
  }
}
@keyframes heartbeat {
  from {
    -webkit-transform: scale(1);
            transform: scale(1);
    -webkit-transform-origin: center center;
            transform-origin: center center;
    -webkit-animation-timing-function: ease-out;
            animation-timing-function: ease-out;
  }
  10% {
    -webkit-transform: scale(0.91);
            transform: scale(0.91);
    -webkit-animation-timing-function: ease-in;
            animation-timing-function: ease-in;
  }
  17% {
    -webkit-transform: scale(0.98);
            transform: scale(0.98);
    -webkit-animation-timing-function: ease-out;
            animation-timing-function: ease-out;
  }
  33% {
    -webkit-transform: scale(0.87);
            transform: scale(0.87);
    -webkit-animation-timing-function: ease-in;
            animation-timing-function: ease-in;
  }
  45% {
    -webkit-transform: scale(1);
            transform: scale(1);
    -webkit-animation-timing-function: ease-out;
            animation-timing-function: ease-out;
  }
}
</style>
