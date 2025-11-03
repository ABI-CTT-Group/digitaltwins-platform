<template>
  <v-alert
      v-show="showAlert"
      text="You’re missing some required information. Please fill in all the required fields."
      title="Required Fields Missing"
      type="error"
  ></v-alert>
  <div>
    <h3 class="text-cyan">Workflow Tool FHIR Annotation</h3>
    <v-divider class="my-2 mb-5" :thickness="3"></v-divider>
    <div v-if="cwlObj">
      <v-form ref="form" class="px-5">
          <h3 class="text-cyan">Tool: {{ annotateTool.name }}</h3>
          <v-divider class="my-2 mb-3" :thickness="2"></v-divider>

          <h4 class="my-2">Tool Inputs</h4>
          <div class="w-100 d-flex flex-row flex-wrap">
            <div v-for="input in annotateTool.inputs" class="d-flex flex-column justify-start w-33">
              <span class="mx-2">{{ input.name }}</span>
                <v-select
                  class="mt-4 mx-2"
                  v-model="input.resource"
                  :items="fhirResources"
                  label="FHIR Resource"
                  required
                  clearable
                ></v-select>
            </div>
          </div>

          <h4 class="my-2">Tool Outputs</h4>
          <div class="w-100 d-flex flex-row flex-wrap">
            <div v-for="output in annotateTool.outputs" class="d-flex flex-column justify-start w-33">
              <span class="mx-2">{{ output.name }}</span>
              <div>
                <v-select
                  class="mt-4 mx-2"
                  v-model="output.resource"
                  :items="fhirResources"
                  :rules="notEmptyRules"
                  label="FHIR Resource"
                  required
                  clearable
                ></v-select>
              </div>
                
              <div
                v-if="output.resource==='Observation'"
              >
                <v-text-field 
                  class="mx-2 my-1"
                  label="Code"
                  v-model="output.code"
                  :rules="notEmptyRules"
                  required
                  clearable
                />
                <v-select
                  class="mx-2 my-1"
                  :items="fhirObservationSytems" 
                  item-title="name"
                  item-value="value"
                  label="Code System"
                  v-model="output.system" 
                  :rules="notEmptyRules"
                  clearable
                ></v-select>
                <v-text-field 
                  class="mx-2 my-1"
                  label="Unit"
                  v-model="output.unit"
                  required
                  clearable
                />
              </div>
            </div>
          </div>
      </v-form>
    </div>

    <!-- <NoData v-else /> -->

    <div v-else class="w-100 no_data flex-grow-1 d-flex flex-column justify-center align-center">
        <v-icon size="64" color="pink-darken-1"> mdi-note-off-outline</v-icon>
        <h2 class="mt-4">No tool CWL file detected</h2>
        <p class="text-grey">
            It seems there are no tool CWL files available. Please upload one or try refreshing to check again.
        </p>
    </div>
  </div>

    <div class="d-flex flex-row justify-center">
        <v-btn
            color="red"
            :text="'close'"
            variant="tonal"
            :width="200"
            rounded="md"
            class="hover-animate ma-5"
            @click="handleClose"
        ></v-btn>
        <v-btn
            color="success"
            :text="'Submit Annotation'"
            variant="tonal"
            :width="200"
            rounded="md"
            class="hover-animate ma-5"
            @click="handleAnnotationSubmit"
        ></v-btn>
    </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, computed, watch} from "vue";
import { PluginResponse } from '@/models/uiTypes';
import { getRepoRootCWLContent } from '@/views/upload-dataset/components/utils';
import NoData from '@/views/upload-dataset/components/NoData.vue';
import { useWorkflowTools } from '@/plugins/plugin_api'; 
import { IAnnotateTool } from "@/models/uiTypes";

const props = defineProps<{
  tool: PluginResponse | undefined
}>();

const showAlert = ref(false)
const annotateTool = ref<IAnnotateTool>({
  name: "",
  inputs:[],
  outputs:[]
})
const cwlObj = ref<any>(null);
const form = ref();

const fhirResources = ref(["Observation", "ImagingStudy", "DocumentReference"])
const fhirObservationSytems = ref([
  {
    name: "LOINC Codes",
    value: "https://loinc.org/"
  },
  {
    name: "SNOMED CT",
    value: "http://snomed.info/sct"
  },
  {
    name: "DCM",
    value: "https://fhir-ru.github.io/codesystem-dicom-dcim.html#4.3.14.431"
  },
  {
    name: "12 Labours Codes",
    value: "https://www.auckland.ac.nz/en/abi/our-research/research-groups-themes/12-Labours.html"
  }
]) 

const notEmptyRules = [
    (v: string) => {
        return !!v || "This field can’t be empty!"
    }
]

onMounted(async ()=>{
    if (!props.tool){
      console.warn("No workflow tool info in annotation stepper.")
      return
    }
    getRepoRootCWLContent(props.tool.repository_url).then((value)=>{
      annotateTool.value.name = value.cwlFile.replace(/\.cwl$/, "");
      cwlObj.value = value.content
    })
})

watch(cwlObj, (newVal) => {
  if (!newVal) return;
  const inputs = newVal['inputs'] || {};
  const outputs = newVal['outputs'] || {};

  annotateTool.value.inputs = Object.keys(inputs).map(k => ({
    name: k,
    resource: ""
  }));

  annotateTool.value.outputs = Object.keys(outputs).map(k => ({
    name: k,
    resource: "", 
    code: "", 
    system: "", 
    unit: "" 
  }));  
  
}, { immediate: true });


const emit = defineEmits(["close", "annotation-submit"])


async function validate(){
    const { valid } = await form.value.validate();
    // onNameBlur();
    // if (valid && nameErr.value?.available && cwlCheck.value){
    //     return true;
    // }

    return valid
}

const handleAnnotationSubmit = async () => {

  const result = await validate();
    if (result){
        emit("annotation-submit", props.tool!.id, annotateTool.value)
        showAlert.value = false
    }else{
        showAlert.value = true
    }
}
const handleClose = () => {
  emit("close")
}
</script>

<style scoped>
.no_data{
  height: 20dvh;
}
</style>

