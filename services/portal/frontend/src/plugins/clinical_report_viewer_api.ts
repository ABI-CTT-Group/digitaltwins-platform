import http from "./http";
import { IClinicalReportViewerDetail } from "@/models/apiTypes";

export async function useClinicalReportViewerDetails(seek_id: string) {
    const detail = http.get<IClinicalReportViewerDetail[]>("/report_viewer/report_detail", { seek_id });
    return detail;
}