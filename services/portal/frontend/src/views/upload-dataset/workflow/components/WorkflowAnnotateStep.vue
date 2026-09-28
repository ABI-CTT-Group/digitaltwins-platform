<template>
  <v-alert
      v-show="showAlert"
      text="You’re missing some required information. Please fill in all the required fields."
      title="Required Fields Missing"
      type="error"
  ></v-alert>
  <div>
    <h3 class="text-cyan">Workflow Annotation</h3>
      <v-divider class="my-2 mb-5" :thickness="3"></v-divider>
  <div v-if="cwlObj">
    <v-form ref="form" class="px-5">
      <div v-for="([key, s], index) in Object.entries(annotateSteps)" :key="key" class="mb-5">
        <h3 class="text-cyan">Step {{index + 1}}: {{ s.name }}</h3>
        <v-divider class="my-2 mb-3" :thickness="2"></v-divider>

        <h4 class="my-2">Workflow Tool *</h4>
        <v-autocomplete
          :custom-filter="toolFilter"
          :items="toolItems" 
          item-title="name"
          item-value="id"
          :label="'Select Workflow Tool for Step '+ (index + 1)"
          @update:model-value="(val)=>handleToolSelect(val, s)" 
          :rules="notEmptyRules"
          clearable>
          <template v-slot:item="{ props: itemProps, item }">
            <v-list-item v-bind="itemProps" :subtitle="item.raw.label"></v-list-item>
          </template>
        </v-autocomplete>

        <div v-if="s.tool_fhir_note">
          <h4 class="my-2 text-amber-darken-2">Tool Inputs</h4>
          <div class="w-100 d-flex flex-row flex-wrap">
            <div v-for="input in s.tool_fhir_note.inputs" class="d-flex flex-column justify-start w-33">
              <span class="mx-2">{{ input.name }} *</span>
                <v-text-field
                  class="mt-4 mx-2"
                  v-model="input.resource"
                  bg-color="cyan-darken-4"  
                  :rules="notEmptyRules"
                  label="FHIR Resource"
                  variant="solo"
                  required
                  readonly
                ></v-text-field>
            </div>
          </div>
        </div>

        <div v-if="s.tool_fhir_note">
          <h4 class="my-2 text-amber-darken-2">Tool Outputs</h4>
          <div class="w-100 d-flex flex-row flex-wrap">
            <div v-for="output in s.tool_fhir_note.outputs" class="d-flex flex-column justify-start w-33">
              <span class="mx-2">{{ output.name }} *</span>
              <div>
                <v-text-field
                  class="mt-4 mx-2"
                  v-model="output.resource"
                  bg-color="cyan-darken-4"  
                  :rules="notEmptyRules"
                  label="FHIR Resource"
                  variant="solo"
                  required
                  readonly
                ></v-text-field>
              </div>
                
              <div
                v-if="output.resource==='Observation'"
              >
                <v-text-field 
                  class="mx-2 my-1"
                  label="Code"
                  v-model="output.code"
                  bg-color="cyan-darken-4" 
                  :rules="notEmptyRules"
                  variant="solo"
                  required
                  readonly
                />
                <v-text-field 
                  class="mx-2 my-1"
                  label="Code System"
                  v-model="output.system"
                  bg-color="cyan-darken-4" 
                  :rules="notEmptyRules"
                  variant="solo"
                  required
                  readonly
                />
                <v-text-field 
                  class="mx-2 my-1"
                  label="Unit"
                  v-model="output.unit"
                  bg-color="cyan-darken-4" 
                  variant="solo"
                  readonly
                />
              </div>
            </div>
          </div>
        </div>
        
      </div>
    </v-form>
  </div>
    <NoData v-else />
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
import { IWrokflowResponse, PluginResponse, IWorkflowStepAnnotation } from '@/models/uiTypes';
import { getRepoContents} from '@/views/upload-dataset/components/utils';
import { GitContent } from '@/models/uiTypes';
import yaml from "js-yaml";
import NoData from '@/views/upload-dataset/components/NoData.vue';
import { useWorkflowTools, useGetWorkflowToolAnnotation} from '@/plugins/plugin_api'; 

const props = defineProps<{
  workflow: IWrokflowResponse | undefined
}>();

const showAlert = ref(false)
const annotateSteps = ref<Array<IWorkflowStepAnnotation>>([])
const cwlObj = ref<any>(null);
const form = ref();
const workflowTools = ref<Array<PluginResponse>>([])
const toolItems = computed(()=>{
  return workflowTools.value.map(tool => ({
    id: tool.id,
    name: tool.name,
    label: tool.label
  }));
})
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
  }
]) 

const notEmptyRules = [
    (v: string) => {
        return !!v || "This field can’t be empty!"
    }
]

onMounted(async ()=>{
    if (!props.workflow){
      console.warn("No workflow info in annotation stepper.")
      return
    }
    getRepoContents(props.workflow.repository_url).then((res)=>{
          const folders = res!.data as GitContent[];
          let cwlFile = "";
          folders.forEach((item: GitContent)=>{
            if(item.type == 'file' && item.name.endsWith(".cwl")){
                  cwlFile = item.name;
                  return;
              }
          })
          getRepoContents(props.workflow!.repository_url, cwlFile).then((res)=>{
              const contentBase64 = res.data.content;
              const content = atob(contentBase64); // base64 → plain text
              try {
                // try to parse YAML format first
                cwlObj.value = yaml.load(content);
              } catch (err) {
                console.warn("YAML parse failed, trying JSON...");
                cwlObj.value = JSON.parse(content); // if it is JSON format
              }
          })
        })
    workflowTools.value = await useWorkflowTools();
})

watch(cwlObj, (newVal) => {
  if (!newVal) return;

  const steps = newVal.steps;
  annotateSteps.value = Object.entries(steps).map(([name, data]: any) => {
    return { name, id: "", uuid: ""};
  });
}, { immediate: true });


const emit = defineEmits(["close", "annotation-submit"])

const handleToolSelect = async (val: string, step: any) => {
  const selectedTool = workflowTools.value.find(tool => tool.id === val);

  if (selectedTool) {
    step.uuid = selectedTool.uuid || "";
    step.id = selectedTool.id;
    const annotation = await useGetWorkflowToolAnnotation(selectedTool.id)
    
    step.tool_fhir_note = annotation.fhir_note ? JSON.parse(annotation.fhir_note) : null;


  } else {
    step.uuid = "";
    step.id = "";
    step.fhir_note = "";
  }
  
}

function toolFilter (itemTitle:string, queryText:string, item:any) {
    const textOne = itemTitle.toLowerCase()
    const textTwo = item.raw.label.toLowerCase()
    const searchText = queryText.toLowerCase()
    return textOne.indexOf(searchText) > -1 || textTwo.indexOf(searchText) > -1
  }

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
        emit("annotation-submit", props.workflow!.id, {
          sparc_note: "",
          fhir_note: JSON.stringify(annotateSteps.value)
        })
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

</style>

