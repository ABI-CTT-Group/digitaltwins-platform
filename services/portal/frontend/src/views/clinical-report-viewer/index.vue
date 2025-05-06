<template>
    <div class="container w-screen h-screen d-flex flex-column align-center">
        <div class="d-flex flex-column w-100 ma-5">
            <h1 class="mx-auto">Clinician Dashboard</h1>

            <v-divider></v-divider>
        </div>
        <div class="flex-grow-1 d-flex flex-column w-75 ma-2 justify-center align-center">
            <v-data-table-server
                v-model:items-per-page="itemsPerPage"
                class="data-table"
                theme="lightTheme"
                :headers="headers"
                :items="serverItems"
                :items-length="totalItems"
                :loading="loading"
                item-value="name"
                @update:options="loadItems"
            >
                <template v-slot:item.name="{ value }">
                    <v-chip
                        class="text-warp"
                        :text="value"
                        size="small"
                    ></v-chip>
                </template>
                <template v-slot:item.date="{ value }">
                    <v-chip
                        :border="`success thin opacity-25`"
                        color="success"
                        :text="value"
                        size="small"
                    ></v-chip>
                </template>
                <template v-slot:item.actions="{ item }">
                    <div class="d-flex ga-2 justify-center">
                        <v-btn variant="tonal" color="cyan"  @click="handleVisualizationlicked(item)">
                            Visualisation
                        </v-btn>
                        <v-btn variant="tonal" color="teal" @click="handleViewPDFClicked(item)">
                            View PDF
                        </v-btn>
                    </div>
                </template>
            </v-data-table-server>
        </div>

        <v-dialog v-model="dialog" class="dialog d-flex justify-center" max-width="900" @after-leave="handleDialogCancel">
          <div class="test d-flex justify-center">
            <!-- <canvas ref="pdfCanvasRef" class="mx-auto"></canvas> -->
            <div ref="divCanvasContainer" class="pdf-page"></div>
          </div>
          
        </v-dialog>
        
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted} from 'vue';
import * as pdfjsLib from "pdfjs-dist";
import { useClinicalReportViewerDetails } from "@/plugins/clinical_report_viewer_api";
import { IClinicalReportViewerDetail } from "@/models/apiTypes";
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

const dialog = ref(false);
const divCanvasContainer = ref<HTMLDivElement>();
const assays = ref([
  {
    id: '',
    date: '',
    pdf: '/ep1_report.pdf'
  },
  {
    id: '',
    date: '',
    pdf: '/ep4_report.pdf'
  },
])

onMounted(async () => {
  const details = await useClinicalReportViewerDetails(route.query.assayId as string);
  details.map((item:IClinicalReportViewerDetail, idx: number) => {
    assays.value[idx].id = item.uuid;
    assays.value[idx].date = item.date;
  });  
});

const renderPDF = async (pdfPath:string) => {
      // const pdfUrl = 'https://pdftron.s3.amazonaws.com/downloads/pl/demo-annotated.pdf';
      const pdfUrl = pdfPath;
      // pdfjsLib.GlobalWorkerOptions.workerSrc = '../../../node_modules/pdfjs-dist/build/pdf.worker.mjs';
      pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdfjs/pdf.worker.mjs';
      const loadingTask = pdfjsLib.getDocument(pdfUrl);
      const pdfDocument = await loadingTask.promise;

      const totalPages = pdfDocument.numPages; // get total pages
      divCanvasContainer.value!.innerHTML = ''; 

      for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
        const page = await pdfDocument.getPage(pageNum);
        const scale = 1.5;
        const viewport = page.getViewport({ scale });
        // Support HiDPI-screens.
        const outputScale = window.devicePixelRatio || 1;

        // create a new canvas element
        const canvas = document.createElement('canvas');
        divCanvasContainer.value!.appendChild(canvas);

        const context = canvas.getContext('2d');
              canvas.width = Math.floor(viewport.width * outputScale);
              canvas.height = Math.floor(viewport.height * outputScale);
              canvas.style.width = Math.floor(viewport.width) + "px";
              canvas.style.height = Math.floor(viewport.height) + "px";
        const transform = outputScale !== 1
              ? [outputScale, 0, 0, outputScale, 0, 0]
              : null;

        const renderContext = {
          canvasContext: context!,
          transform: transform!,
          viewport: viewport,
        };
        await page.render(renderContext);
      }
    };

const handleDialogCancel = () => {
    dialog.value = false;
};


  const FakeAPI = {
    async fetch ({ page, itemsPerPage, sortBy }:any) {
      return new Promise(resolve => {
        setTimeout(() => {
          const start = (page - 1) * itemsPerPage
          const end = start + itemsPerPage
          const items = assays.value.slice()
          if (sortBy.length) {
            const sortKey = sortBy[0].key
            const sortOrder = sortBy[0].order
            items.sort((a:any, b:any) => {
              const aValue = a[sortKey]
              const bValue = b[sortKey]
              return sortOrder === 'desc' ? bValue - aValue : aValue - bValue
            })
          }
          const paginated = items.slice(start, end)
          resolve({ items: paginated, total: items.length })
        }, 500)
      })
    },
  }
  const itemsPerPage = ref(5)
  const headers = ref([
    { title: 'Patient ID', key: 'id', align: 'center' },
    { title: 'Date Generated', key: 'date', align: 'center', sortable: false },
    { title: 'Actions', key: 'actions', align: 'center', sortable: false }
  ])
  const serverItems = ref([])
  const loading = ref(true)
  const totalItems = ref(0)
  function loadItems ({ page, itemsPerPage, sortBy }:any) {
    loading.value = true
    FakeAPI.fetch({ page, itemsPerPage, sortBy }).then(({ items, total }:any) => {
      serverItems.value = items
      totalItems.value = total
      loading.value = false
    })
  }

  async function handleViewPDFClicked(item:any) {
    console.log('View PDF clicked', item)
    dialog.value = true
    await renderPDF(item.pdf);
  }

  function handleVisualizationlicked(item:any) {
    console.log('Visualization clicked', item.id)
    console.log('Visualization clicked', route.query.assayId)
    router.push({name: "TumourAssistedStudy", query: { assayId:route.query.assayId, patientId: item.id }});
  }
</script>

<style scoped>
.container{
  background: #556270;  
    background: -webkit-linear-gradient(to right, #FF6B6B, #556270);  
    background: linear-gradient(to right, #FF6B6B, #556270); 
}
.text-warp{
    
  word-wrap: break-word;
  word-break: break-word;
}
.data-table {
  /* min-width: 600px; */
  /* max-width: 450px; */
}
.dialog{
  background-color: rgba(0, 0, 0, 0.5);
}
.test {
  max-height: 100%;   /* 使其填充父元素 */
  overflow-y: auto;   /* 超出时垂直方向滚动 */
}
</style>