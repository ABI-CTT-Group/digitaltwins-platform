import { ref, watch } from 'vue';
import { useToast } from 'vue-toastification';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDashboardPageStore } from '@/store/dashboard_page_store';
import {
    useDashboardGetAssayConfigDetails,
    useDashboardGetAssayLaunch,
    useDashboardWorkflowDetail,
    useDashboardProgrammes,
    useDashboardCategoryChildren,
    useSaveAssayDetails,
} from '@/bootstrap/dashboard_api';
import { DashboardCategory, AssayDetails } from '@/models/types';
import { reWriteCategoryDetails } from '@/views/study/utils';
import { getApiErrorMessage } from '@/utils/common';

const BREADCRUMB_ORDER = ['Programmes', 'Projects', 'Investigations', 'Studies', 'Assays'];

export function useDashboardView(isClinicianView: boolean) {
    const router = useRouter();
    const toast = useToast();

    const dashboardProgrammes = ref<DashboardCategory[]>();
    const dashboardCategoryChildren = ref<DashboardCategory[]>();

    const getDashboardProgrammes = async () => {
        dashboardProgrammes.value = await useDashboardProgrammes();
    };
    const getDashboardCategoryChildren = async (seek_id: string, category: string) => {
        dashboardCategoryChildren.value = await useDashboardCategoryChildren(seek_id, category);
    };
    const saveAssayDetails = async (body: AssayDetails): Promise<boolean> => {
        return await useSaveAssayDetails(body);
    };

    const {
        currentCategory,
        breadCrumbsCategory,
        exploredCard,
        currentCategoryData,
        breadCrumbsItems,
        detailsRenderItems,
        assayExecute,
        allAssayDetailsOfStudy,
        currentAssayDetails,
    } = storeToRefs(useDashboardPageStore());
    const {
        setCurrentCategory,
        setBreadCrumbsCategory,
        setExploredCard,
        setCurrentCategoryData,
        setDetailsRenderItems,
        setAssayExecute,
        setAssayLaunching,
        setAllAssayDetailsOfStudy,
        setCurrentAssayDetails,
    } = useDashboardPageStore();

    const downloadZipProgressValue = ref(0);
    const downloadDialog = ref(false);
    const submitDialog = ref(false);
    const submitState = ref('waiting');

    const handleBreadCrumbsClick = (res: PointerEvent) => {
        const clickedCrumb = (res.target as HTMLElement).innerText;
        if (clickedCrumb === 'Assays' || clickedCrumb.includes('/') || clickedCrumb === currentCategory.value) return;

        setCurrentCategory(clickedCrumb);
        const data = exploredCard.value.find(item => item.category === clickedCrumb)?.data;
        if (data) {
            setCurrentCategoryData(data);
        } else {
            setCurrentCategoryData(dashboardProgrammes.value!);
        }

        const index = breadCrumbsItems.value.findIndex(item => item.title === clickedCrumb);
        const detailsIndex = detailsRenderItems.value.categories.findIndex(item => item.category === clickedCrumb);

        if (index !== 0) {
            setBreadCrumbsCategory(breadCrumbsItems.value[index - 1].title);
            setDetailsRenderItems(
                detailsRenderItems.value.categories.slice(0, detailsIndex),
                detailsRenderItems.value.categories[detailsIndex - 1].description,
            );
        } else {
            setBreadCrumbsCategory(clickedCrumb);
            setDetailsRenderItems([], '');
        }
        breadCrumbsItems.value.splice(index + 1);
    };

    const handleAssayEditClicked = (_seek_id: string, _name: string) => {
        setCurrentAssayDetails(allAssayDetailsOfStudy.value[_seek_id]);
    };

    const handleAssaySave = async () => {
        try {
            const success = await saveAssayDetails(currentAssayDetails.value!);
            if (success) {
                currentAssayDetails.value!.isAssayReadyToLaunch = true;
                setAllAssayDetailsOfStudy(currentAssayDetails.value!.seekId, currentAssayDetails.value!);
                toast.success('Assay configuration saved successfully.');
            } else {
                toast.error('Save failed. Please try again.');
            }
        } catch (e: any) {
            toast.error(getApiErrorMessage(e, 'Save'));
        }
    };

    const handleAssayUploadClicked = async (_assay_seek_id: string) => {
        submitDialog.value = true;
        submitState.value = 'waiting';
        toast.info('Submit feature is being migrated to the portal backend; not available right now.');
        submitState.value = 'unavailable';
    };

    const handleAssayDownloadClicked = async (_assay_seek_id: string) => {
        downloadDialog.value = true;
        downloadZipProgressValue.value = 0;
        toast.info('Download feature is being migrated to the portal backend; not available right now.');
    };

    const handleAssayVerifyClicked = async (assay_seek_id: string) => {
        const workflowUUID = allAssayDetailsOfStudy.value[assay_seek_id].workflow.uuid;
        window.open(`${import.meta.env.VITE_JUPYTER_BASE_URL}/lab/tree/workflow_outputs/${workflowUUID}/verify.ipynb`, '_blank');
    };

    const handleAssayMonitorClicked = async (assay_seek_id: string) => {
        window.open(assayExecute.value![assay_seek_id].url, '_blank');
    };

    const handleAssayLaunchClicked = async (assay_seek_id: string) => {
        setCurrentAssayDetails(allAssayDetailsOfStudy.value[assay_seek_id]);
        setAssayLaunching(assay_seek_id, true);
        try {
            const res = await useDashboardGetAssayLaunch(assay_seek_id);
            if (!res) {
                toast.warning('Launch is not available for this assay. Please check the configuration.');
                return;
            }
            if (res.message) {
                toast.info(res.message, { timeout: 6000 });
            } else if (res.type === 'airflow') {
                setAssayExecute(assay_seek_id, 'Monitor', res.data);
                toast.success('Workflow launched successfully. Click Monitor to track progress.');
            } else if (res.type === 'EP3 workflow launch') {
                window.open(res.data, '_blank');
            }
        } catch (e: any) {
            toast.error(getApiErrorMessage(e, 'Launch'));
        } finally {
            setAssayLaunching(assay_seek_id, false);
        }
    };

    const handleAssayExpandClicked = (assay_seek_id: string, _name: string) => {
        router.push({ name: 'LaunchedAssayOverview', query: { assayId: assay_seek_id } });
    };

    const handleExploreClicked = async (seek_id: string, name: string, category: string, des: string) => {
        try {
            const explored = exploredCard.value.find(item => item.category === category);
            if (!explored) {
                setExploredCard(category, currentCategoryData.value);
            } else {
                explored.data = currentCategoryData.value;
            }

            await getDashboardCategoryChildren(seek_id, category);

            detailsRenderItems.value.categories.push({ category, name, description: reWriteCategoryDetails(category) });
            detailsRenderItems.value.description = des;

            setBreadCrumbsCategory(category);

            const index = BREADCRUMB_ORDER.findIndex(item => item === category);
            setCurrentCategory(BREADCRUMB_ORDER[index + 1]);
            breadCrumbsItems.value.push({ title: currentCategory.value, disabled: false });

            if (category === 'Programmes') {
                dashboardCategoryChildren.value!.sort((a, b) => a.name.localeCompare(b.name));
            }

            setCurrentCategoryData(dashboardCategoryChildren.value!);
        } catch (e: any) {
            toast.error(getApiErrorMessage(e, 'Explore'));
        }
    };

    watch(() => currentCategoryData.value, (newVal) => {
        if (!newVal || newVal.length === 0 || currentCategory.value !== 'Assays') return;
        if (newVal[0].category !== 'Assays') return;

        assayExecute.value = {};
        allAssayDetailsOfStudy.value = {};

        const loadSequentially = async () => {
            for (const item of currentCategoryData.value) {
                const details = await useDashboardGetAssayConfigDetails(item.seekId);
                setAssayExecute(item.seekId, 'Launch', '');
                if (details) {
                    setAllAssayDetailsOfStudy(item.seekId, details);
                } else {
                    const workflowDetail = await useDashboardWorkflowDetail(item.workflow_seek_id!);
                    workflowDetail.type = item.tag ?? 'unknown workflow type';
                    setAllAssayDetailsOfStudy(item.seekId, {
                        uuid: '',
                        seekId: item.seekId,
                        workflow: workflowDetail,
                        numberOfParticipants: [],
                        isAssayReadyToLaunch: false,
                    });
                }
            }
        };
        loadSequentially();
    });

    const handleHelpClick = () => {
        window.open('https://github.com/ABI-CTT-Group/DigitalTWINS-Portal?tab=readme-ov-file#how-to-use-the-study-dashboard', '_blank');
    };

    const initDashboard = async (filterFn: (item: DashboardCategory) => boolean) => {
        currentCategoryData.value.length = 0;
        breadCrumbsItems.value = [{ title: 'Programmes', disabled: false }];
        setCurrentCategory('Programmes');
        exploredCard.value = [];
        detailsRenderItems.value = { categories: [], description: '' };
        await getDashboardProgrammes();
        currentCategoryData.value = dashboardProgrammes.value!.filter(filterFn);
    };

    return {
        isClinicianView,
        currentCategory,
        breadCrumbsCategory,
        currentCategoryData,
        breadCrumbsItems,
        detailsRenderItems,
        downloadZipProgressValue,
        downloadDialog,
        submitDialog,
        submitState,
        handleBreadCrumbsClick,
        handleAssayEditClicked,
        handleAssaySave,
        handleAssayUploadClicked,
        handleAssayDownloadClicked,
        handleAssayVerifyClicked,
        handleAssayMonitorClicked,
        handleAssayLaunchClicked,
        handleAssayExpandClicked,
        handleExploreClicked,
        handleHelpClick,
        initDashboard,
    };
}
