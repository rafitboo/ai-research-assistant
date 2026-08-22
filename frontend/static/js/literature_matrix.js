const API_BASE = window.API_BASE_URL || "http://127.0.0.1:8000";
const API = `${API_BASE}/api/literature-matrix`;
const TOKEN = window.AUTH_TOKEN;

let currentMatrixId = null;
let currentMatrix = null;


function headers() {
    return {
        "Authorization": `Bearer ${TOKEN}`,
        "Content-Type": "application/json"
    };
}


async function api(url, options = {}) {
    const baseUrl = window.API_BASE_URL || "http://127.0.0.1:8000";
    const fullUrl = url.startsWith("http") ? url : `${baseUrl}${url.startsWith("/") ? "" : "/"}${url}`;

    const token = window.AUTH_TOKEN 
        || (typeof headers === "function" ? headers().Authorization : null);

    const defaultHeaders = {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": token.startsWith("Bearer ") ? token : `Bearer ${token}` } : {})
    };

    const response = await fetch(fullUrl, {
        ...options,
        headers: {
            ...defaultHeaders,
            ...(options.headers || {})
        }
    });

    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const data = await response.json();
            message = typeof data.detail === "string" ? data.detail : (data.message || message);
        } catch (_) {}
        throw new Error(message);
    }

    if (response.status === 204) return null;
    return response.json();
}


/* --------------------------------------------------
   Load matrices
-------------------------------------------------- */

async function selectMatrixCard(id) {
    // 1. Clear selection outline from all cards
    document.querySelectorAll(".matrix-card").forEach(card => {
        card.classList.remove("border-indigo-600", "ring-2", "ring-indigo-400", "bg-indigo-50/40");
    });

    // 2. Add active highlight to chosen card
    const card = document.getElementById(`matrix-card-${id}`);
    if (card) {
        card.classList.add("border-indigo-600", "ring-2", "ring-indigo-400", "bg-indigo-50/40");
    }

    // 3. Load workspace data
    await loadMatrix(id);
}

async function loadMatrices() {
    try {
        const matrices = await api(API);
        const container = document.getElementById("matrixGrid");
        if (!container) return;

        if (!matrices || matrices.length === 0) {
            container.innerHTML = `<p class="text-slate-500 text-sm col-span-3">No literature matrices found. Click 'Create Matrix' to start.</p>`;
            return;
        }

        container.innerHTML = matrices.map(matrix => `
            <div 
                id="matrix-card-${matrix.id}"
                onclick="selectMatrixCard(${matrix.id})"
                class="matrix-card cursor-pointer p-4 border border-slate-200 rounded-xl hover:border-indigo-500 hover:shadow-md transition-all bg-white"
            >
                <div class="flex items-center justify-between">
                    <h3 class="font-bold text-slate-800 text-base">${escapeHtml(matrix.title)}</h3>
                </div>
                <p class="text-slate-500 text-xs mt-2 line-clamp-2">${escapeHtml(matrix.description || "No description provided.")}</p>
            </div>
        `).join("");

    } catch (error) {
        alert(error.message);
    }
}


/* --------------------------------------------------
   Create matrix
-------------------------------------------------- */

function openCreateMatrixModal() {

    document
        .getElementById("createMatrixModal")
        .classList.remove("hidden");
}


function closeCreateMatrixModal() {

    document
        .getElementById("createMatrixModal")
        .classList.add("hidden");
}


async function createMatrix() {
    const title = document.getElementById("newMatrixTitle").value.trim();
    const description = document.getElementById("newMatrixDescription").value.trim();

    if (!title) {
        alert("Enter a matrix title.");
        return;
    }

    try {
        const matrix = await api(API, {
            method: "POST",
            body: JSON.stringify({
                title,
                description
            })
        });

        closeCreateMatrixModal();

        // Clear input fields
        document.getElementById("newMatrixTitle").value = "";
        document.getElementById("newMatrixDescription").value = "";

        // Reload cards grid and automatically select the newly created matrix
        await loadMatrices();
        await selectMatrixCard(matrix.id);

    } catch (error) {
        alert(error.message);
    }
}


/* --------------------------------------------------
   Load matrix
-------------------------------------------------- */

async function loadMatrix(id) {

    if (!id) {

        document
            .getElementById("matrixWorkspace")
            .classList.add("hidden");

        return;
    }

    try {

        currentMatrixId = id;

        currentMatrix =
            await api(`${API}/${id}`);

        renderMatrix();

        document
            .getElementById("matrixWorkspace")
            .classList.remove("hidden");

    } catch (error) {

        alert(error.message);
    }
}


/* --------------------------------------------------
   Render matrix
-------------------------------------------------- */

function renderMatrix() {

    document
        .getElementById("matrixTitle")
        .textContent = currentMatrix.title;

    document
        .getElementById("matrixDescription")
        .textContent =
        currentMatrix.description || "No description";


    const header =
        document.getElementById("matrixHeader");

    header.innerHTML = "";


    const headerRow =
        document.createElement("tr");


    const paperHeader =
        document.createElement("th");

    paperHeader.className =
        "text-left px-5 py-4 font-black sticky left-0 bg-slate-50";

    paperHeader.textContent =
        "Paper";

    headerRow.appendChild(paperHeader);


currentMatrix.columns.forEach(column => {
        const th = document.createElement("th");
        th.className = "text-left px-5 py-4 font-black min-w-[250px]";

        th.innerHTML = `
            <div class="flex items-center justify-between gap-2">
                <div>
                    <span>${escapeHtml(column.name)}</span>
                    ${column.is_custom ? '<span class="ml-2 text-xs text-indigo-500">CUSTOM</span>' : ''}
                </div>
                <button 
                    type="button" 
                    onclick="deleteColumn(${column.id})"
                    class="text-slate-400 hover:text-red-500 font-bold px-1 rounded transition-colors text-base"
                    title="Delete Column"
                >
                    &times;
                </button>
            </div>
        `;

        headerRow.appendChild(th);
    });


    header.appendChild(headerRow);


    const body =
        document.getElementById("matrixBody");

    body.innerHTML = "";


    currentMatrix.papers.forEach(paper => {

        const tr =
            document.createElement("tr");

        tr.className =
            "border-b hover:bg-slate-50";


        const titleCell =
            document.createElement("td");

        titleCell.className =
            "px-5 py-4 font-bold text-slate-900 align-top sticky left-0 bg-white";

        titleCell.textContent =
            paper.title;

        tr.appendChild(titleCell);


        currentMatrix.columns.forEach(column => {

            const td =
                document.createElement("td");

            td.className =
                "px-4 py-4 align-top";


            const cell =
                paper.cells[column.id];


            const textarea =
                document.createElement("textarea");

            textarea.value =
                cell?.value || "";

            textarea.rows = 5;

            textarea.className =
                "w-full min-w-[220px] border border-slate-200 rounded-xl p-3 text-sm resize-y focus:ring-2 focus:ring-indigo-400 outline-none";


            textarea.addEventListener("blur", () => 
                saveCell(paper.paper_id || paper.id, column.id, textarea.value)
            );


            const source =
                document.createElement("div");

            source.className =
                "text-[10px] mt-1 text-slate-400";

            source.textContent =
                cell?.source
                    ? `Source: ${cell.source}`
                    : "";


            td.appendChild(textarea);
            td.appendChild(source);

            tr.appendChild(td);

        });


        body.appendChild(tr);

    });
}


/* --------------------------------------------------
   Save cell
-------------------------------------------------- */

async function saveCell(paperId, columnId, value) {
    if (!currentMatrixId) return;

    try {
        await api(`${API}/${currentMatrixId}/cells`, {
            method: "POST",
            body: JSON.stringify({
                paper_id: paperId,
                column_id: columnId,
                value: value
            })
        });
    } catch (error) {
        alert(error.message);
    }
}


/* --------------------------------------------------
   Papers
-------------------------------------------------- */

async function openPaperModal() {

    document
        .getElementById("paperModal")
        .classList.remove("hidden");


    const container =
        document.getElementById("paperSelection");

    container.innerHTML =
        "Loading papers...";


    try {

        const response =
            await fetch(
                `${window.API_BASE_URL}/api/papers/`,
                {
                    headers: {
                        "Authorization":
                            `Bearer ${TOKEN}`
                    }
                }
            );


        if (!response.ok) {

            throw new Error(
                "Failed to load papers"
            );
        }


        const papers =
            await response.json();


        const selected =
            new Set(
                currentMatrix.papers
                    .map(paper => paper.paper_id)
            );


        container.innerHTML = "";


        papers.forEach(paper => {

            const wrapper =
                document.createElement("label");

            wrapper.className =
                "flex items-center gap-3 p-3 border rounded-xl hover:bg-slate-50 cursor-pointer";


            wrapper.innerHTML = `
                <input
                    type="checkbox"
                    value="${paper.id}"
                    ${selected.has(paper.id) ? "checked" : ""}
                    class="paper-checkbox"
                >

                <div>
                    <p class="font-bold text-sm">
                        ${escapeHtml(paper.title)}
                    </p>

                    <p class="text-xs text-slate-500">
                        ${escapeHtml(paper.author || "Unknown author")}
                        ${paper.year ? ` • ${paper.year}` : ""}
                    </p>
                </div>
            `;


            container.appendChild(wrapper);

        });

    } catch (error) {

        container.innerHTML =
            `<p class="text-red-500">${escapeHtml(error.message)}</p>`;
    }
}


function closePaperModal() {

    document
        .getElementById("paperModal")
        .classList.add("hidden");
}


async function addSelectedPapers() {

    const checkboxes =
        document.querySelectorAll(
            ".paper-checkbox:checked"
        );


    const ids =
        Array.from(checkboxes)
            .map(input => Number(input.value));


    if (ids.length < 2) {

        alert(
            "Please select at least 2 papers."
        );

        return;
    }


    try {

        await api(
            `${API}/${currentMatrixId}/papers`,
            {
                method: "POST",
                body: JSON.stringify({
                    paper_ids: ids
                })
            }
        );


        closePaperModal();

        await loadMatrix(currentMatrixId);

    } catch (error) {

        alert(error.message);
    }
}


/* --------------------------------------------------
   Custom columns
-------------------------------------------------- */

function openColumnModal() {

    document
        .getElementById("columnModal")
        .classList.remove("hidden");
}


function closeColumnModal() {

    document
        .getElementById("columnModal")
        .classList.add("hidden");
}


async function addCustomColumn() {

    const name =
        document
            .getElementById("newColumnName")
            .value
            .trim();


    if (!name) {

        alert("Enter a column name.");
        return;
    }


    try {

        await api(
            `${API}/${currentMatrixId}/columns`,
            {
                method: "POST",
                body: JSON.stringify({
                    name
                })
            }
        );


        closeColumnModal();

        document
            .getElementById("newColumnName")
            .value = "";


        await loadMatrix(currentMatrixId);

    } catch (error) {

        alert(error.message);
    }
}


/* --------------------------------------------------
   AI analysis
-------------------------------------------------- */

async function analyzeMatrix() {

    if (!currentMatrixId) {
        return;
    }


    if (currentMatrix.papers.length < 2) {

        alert(
            "Add at least 2 papers first."
        );

        return;
    }


    const button =
        event?.target;


    if (button) {

        button.disabled = true;
        button.textContent =
            "✨ Analyzing...";
    }


    try {

        await api(
            `${API}/${currentMatrixId}/analyze`,
            {
                method: "POST"
            }
        );


        alert(
            "AI comparison completed."
        );


        await loadMatrix(currentMatrixId);

    } catch (error) {

        alert(error.message);

    } finally {

        if (button) {

            button.disabled = false;
            button.textContent =
                "✨ AI Analyze";
        }
    }
}

async function deleteColumn(columnId) {
    if (!confirm("Are you sure you want to delete this column? All cell data in this column will be permanently deleted.")) {
        return;
    }

    try {
        await api(`${API}/${currentMatrixId}/columns/${columnId}`, {
            method: "DELETE"
        });
        loadMatrix(currentMatrixId); // Refresh matrix table
    } catch (error) {
        alert(error.message);
    }
}


/* --------------------------------------------------
   CSV
-------------------------------------------------- */

function exportMatrix() {
    if (!currentMatrixId) {
        alert("No active matrix loaded.");
        return;
    }
    downloadCSV(currentMatrixId);
}


async function downloadCSV(matrixId) {  
    try {  
        // Check window variable, localStorage, and sessionStorage for the token
        const token = window.AUTH_TOKEN 
            || localStorage.getItem("token") 
            || localStorage.getItem("TOKEN") 
            || sessionStorage.getItem("token");

        if (!token) {  
            alert("You are not logged in. Please refresh or log in again.");  
            return;  
        }

        const baseUrl = window.API_BASE_URL || "";
        const response = await fetch(  
            `${baseUrl}/api/literature-matrix/${matrixId}/export`,  
            {  
                method: "GET",  
                headers: {  
                    "Authorization": `Bearer ${token}`  
                }  
            }  
        );

        if (!response.ok) {  
            alert(`Failed to download CSV (${response.status})`);  
            return;  
        }

        const blob = await response.blob();  
        const url = window.URL.createObjectURL(blob);  
        const a = document.createElement("a");  
        a.href = url;  
        a.download = `literature_matrix_${matrixId}.csv`;  
        document.body.appendChild(a);  
        a.click();  
        a.remove();  
        window.URL.revokeObjectURL(url);  
    } catch (error) {  
        console.error("CSV download failed:", error);  
        alert("Failed to download CSV.");  
    }  
}


/* --------------------------------------------------
   Security helper
-------------------------------------------------- */

function escapeHtml(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


/* --------------------------------------------------
   Initial load
-------------------------------------------------- */

document.addEventListener("DOMContentLoaded", async () => {
    await loadMatrices();

    const urlParams = new URLSearchParams(window.location.search);
    const matrixId = urlParams.get("matrix_id") || urlParams.get("id");

    if (matrixId) {
        await selectMatrixCard(Number(matrixId));
    }
});