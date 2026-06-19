import React, { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { toast } from "sonner";

export default function PdfExportButton({ targetId = "dashboard-main", filename }) {
  const [loading, setLoading] = useState(false);

  const exportPdf = async () => {
    const el = document.getElementById(targetId);
    if (!el) {
      toast.error("Nothing to export yet");
      return;
    }
    setLoading(true);
    try {
      const canvas = await html2canvas(el, {
        backgroundColor: "#09090b",
        scale: 1.4,
        useCORS: true,
        logging: false,
        windowWidth: el.scrollWidth,
        windowHeight: el.scrollHeight,
      });
      const imgData = canvas.toDataURL("image/jpeg", 0.85);
      const pdf = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pageWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;
      pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
      while (heightLeft > 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }
      pdf.save(filename || `stock-sentinel-${Date.now()}.pdf`);
      toast.success("PDF exported");
    } catch (e) {
      toast.error("PDF export failed: " + (e.message || ""));
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={exportPdf}
      disabled={loading}
      data-testid="export-pdf-btn"
      className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700 disabled:opacity-50 transition-colors"
    >
      {loading ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
      {loading ? "Generating…" : "Export PDF"}
    </button>
  );
}
