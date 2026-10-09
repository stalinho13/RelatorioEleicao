import { ChangeEvent, DragEvent, ReactNode, useEffect, useRef, useState } from "react";

type IconName =
  | "document"
  | "history"
  | "texture"
  | "vector"
  | "help"
  | "menu"
  | "close"
  | "upload"
  | "chevron"
  | "sparkles"
  | "file"
  | "check"
  | "download"
  | "building";

type Texture = "none" | "paper" | "red";

function Icon({ name, className = "size-5" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, ReactNode> = {
    document: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
        <path d="M14 2v6h6M8 13h8M8 17h6" />
      </>
    ),
    history: (
      <>
        <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
        <path d="M3 3v5h5M12 7v5l3 2" />
      </>
    ),
    texture: (
      <>
        <path d="M4 5.5C6 4 8 4 10 5.5s4 1.5 6 0 3-.8 4-.2M4 11c2-1.5 4-1.5 6 0s4 1.5 6 0 3-.8 4-.2M4 16.5c2-1.5 4-1.5 6 0s4 1.5 6 0 3-.8 4-.2" />
      </>
    ),
    vector: (
      <>
        <circle cx="5" cy="5" r="2" />
        <circle cx="19" cy="5" r="2" />
        <circle cx="12" cy="19" r="2" />
        <path d="m6.7 6 4.2 11M17.3 6l-4.2 11M7 5h10" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9.7 9a2.5 2.5 0 1 1 3.4 2.3c-.8.4-1.1.9-1.1 1.7M12 17h.01" />
      </>
    ),
    menu: <path d="M4 7h16M4 12h16M4 17h16" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    upload: (
      <>
        <path d="M12 16V4M7 9l5-5 5 5" />
        <path d="M5 15v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    sparkles: (
      <>
        <path d="m12 3-1 3.2L8 7.5l3 1.3 1 3.2 1-3.2 3-1.3-3-1.3L12 3Z" />
        <path d="m18 14-.7 2.2-2.3.8 2.3.8L18 20l.7-2.2L21 17l-2.3-.8L18 14ZM5.5 12l-.7 2-1.8.7 1.8.7.7 2 .7-2 1.8-.7-1.8-.7-.7-2Z" />
      </>
    ),
    file: (
      <>
        <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7Z" />
        <path d="M14 2v5h5" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    download: (
      <>
        <path d="M12 3v12M7 10l5 5 5-5" />
        <path d="M5 19h14" />
      </>
    ),
    building: (
      <>
        <path d="M4 21h16M6 21V8l6-4 6 4v13M9 11h2M13 11h2M9 15h2M13 15h2" />
      </>
    ),
  };

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

const menuItems: { label: string; icon: IconName; active?: boolean }[] = [
  { label: "Nova Pauta", icon: "document", active: true },
  { label: "Histórico de PDFs", icon: "history" },
  { label: "Configurações de Textura", icon: "texture" },
  { label: "Vetorizar Logotipos", icon: "vector" },
];

const textures: { value: Texture; label: string; detail: string }[] = [
  { value: "none", label: "Sem textura", detail: "Fundo branco" },
  { value: "paper", label: "Papel", detail: "Textura sutil" },
  { value: "red", label: "Vermelha", detail: "Fundo editorial" },
];

function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      {open && (
        <button
          aria-label="Fechar menu"
          className="fixed inset-0 z-30 bg-slate-950/25 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-slate-200/80 bg-white px-4 py-5 transition-transform duration-300 lg:static lg:w-64 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-red-600 text-white shadow-lg shadow-red-600/20">
              <Icon name="document" className="size-5" />
            </div>
            <div>
              <div className="text-lg font-bold tracking-tight text-slate-900">
                pauta<span className="text-red-600">.</span>pdf
              </div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Document Studio
              </div>
            </div>
          </div>
          <button
            aria-label="Fechar menu"
            className="grid size-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 lg:hidden"
            onClick={onClose}
          >
            <Icon name="close" />
          </button>
        </div>

        <div className="mt-9 px-3 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">
          Workspace
        </div>
        <nav className="mt-3 space-y-1.5">
          {menuItems.map((item) => (
            <button
              key={item.label}
              className={`group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${
                item.active
                  ? "bg-red-50 text-red-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
              onClick={onClose}
            >
              <span
                className={`grid size-8 place-items-center rounded-lg ${
                  item.active
                    ? "bg-white text-red-600 shadow-sm"
                    : "text-slate-400 group-hover:text-slate-700"
                }`}
              >
                <Icon name={item.icon} className="size-[18px]" />
              </span>
              {item.label}
              {item.active && <span className="ml-auto size-1.5 rounded-full bg-red-600" />}
            </button>
          ))}
        </nav>

        <div className="mt-auto">
          <div className="mx-1 mb-4 rounded-2xl bg-slate-950 p-4 text-white">
            <div className="mb-4 grid size-8 place-items-center rounded-lg bg-white/10">
              <Icon name="help" className="size-4" />
            </div>
            <div className="text-sm font-semibold">Precisa de ajuda?</div>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              Consulte o guia rápido para criar pautas perfeitas.
            </p>
            <button className="mt-3 text-xs font-semibold text-white underline decoration-slate-600 underline-offset-4">
              Acessar documentação
            </button>
          </div>
          <div className="flex items-center gap-3 border-t border-slate-100 px-2 pt-4">
            <div className="grid size-9 place-items-center rounded-full bg-red-100 text-xs font-bold text-red-700">
              AD
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-slate-800">Admin</div>
              <div className="truncate text-xs text-slate-400">Plano profissional</div>
            </div>
            <Icon name="chevron" className="size-4 text-slate-400" />
          </div>
        </div>
      </aside>
    </>
  );
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [city, setCity] = useState("");
  const [content, setContent] = useState("");
  const [texture, setTexture] = useState<Texture>("paper");
  const [file, setFile] = useState<File | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [generationState, setGenerationState] = useState<
    "idle" | "generating" | "success" | "error"
  >("idle");
  const [generationMessage, setGenerationMessage] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (logoUrl) URL.revokeObjectURL(logoUrl);
    };
  }, [logoUrl]);

  function receiveFile(selected?: File) {
    if (!selected) return;
    if (!["image/svg+xml", "image/png"].includes(selected.type)) {
      setGenerationState("error");
      setGenerationMessage("Selecione um logotipo SVG ou PNG.");
      return;
    }
    if (selected.size > 5 * 1024 * 1024) {
      setGenerationState("error");
      setGenerationMessage("O logotipo deve ter no máximo 5 MB.");
      return;
    }
    if (logoUrl) URL.revokeObjectURL(logoUrl);
    setFile(selected);
    setLogoUrl(URL.createObjectURL(selected));
    setGenerationState("idle");
    setGenerationMessage("");
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    receiveFile(event.dataTransfer.files[0]);
  }

  async function renderPdf() {
    if (!city.trim()) {
      setGenerationState("error");
      setGenerationMessage('Informe a cidade e a UF, por exemplo: "Pelotas, RS".');
      return;
    }

    const form = new FormData();
    form.append("city", city.trim());
    form.append("content", content.trim());
    form.append("texture", texture);
    if (file) form.append("logo", file);

    setGenerationState("generating");
    setGenerationMessage(
      "Consultando os dados eleitorais e diagramando o documento. Isso pode levar alguns minutos.",
    );

    try {
      const apiBase = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
      const response = await fetch(`${apiBase}/api/pautas`, {
        method: "POST",
        body: form,
      });

      if (!response.ok) {
        let message = "Não foi possível gerar o PDF.";
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload.detail) message = payload.detail;
        } catch {
          // A API pode estar indisponível e devolver uma resposta sem JSON.
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const disposition = response.headers.get("content-disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const fallbackName = `${city
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")}-pauta.pdf`;
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = encodedName ? decodeURIComponent(encodedName) : fallbackName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);

      setGenerationState("success");
      setGenerationMessage("PDF gerado e baixado com sucesso.");
    } catch (error) {
      setGenerationState("error");
      setGenerationMessage(
        error instanceof Error
          ? error.message
          : "Ocorreu um erro inesperado durante a geração.",
      );
    }
  }

  const previewTitle = city.trim() || "Nome da Cidade";
  const previewText =
    content.trim() ||
    "O conteúdo da sua pauta aparecerá aqui conforme você preenche o formulário. Organize as informações de forma clara e objetiva.";

  return (
    <div className="flex min-h-screen bg-[#f7f8fa] text-slate-900">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200/70 bg-white/85 px-4 backdrop-blur-xl sm:px-6 lg:hidden">
          <button
            aria-label="Abrir menu"
            className="grid size-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-700"
            onClick={() => setSidebarOpen(true)}
          >
            <Icon name="menu" />
          </button>
          <div className="font-bold tracking-tight">
            pauta<span className="text-red-600">.</span>pdf
          </div>
          <div className="size-10" />
        </header>

        <div className="mx-auto max-w-[1480px] px-4 py-7 sm:px-6 lg:px-9 lg:py-10 xl:px-12">
          <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-red-600">
                <span className="h-px w-5 bg-red-500" />
                Novo documento
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
                Gerar Pauta da Cidade
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
                Preencha as informações, personalize a identidade visual e acompanhe a
                prévia do documento em tempo real.
              </p>
            </div>
            <div className="flex items-center gap-2 self-start rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 sm:self-auto">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
              </span>
              Motor de PDF online
            </div>
          </div>

          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(440px,0.85fr)]">
            <section className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-7">
              <div className="mb-7 flex items-center gap-3 border-b border-slate-100 pb-5">
                <span className="grid size-9 place-items-center rounded-xl bg-red-50 text-red-600">
                  <Icon name="document" className="size-[18px]" />
                </span>
                <div>
                  <h2 className="text-base font-bold text-slate-900">Dados da pauta</h2>
                  <p className="text-xs text-slate-400">Campos marcados são obrigatórios</p>
                </div>
              </div>

              <div className="space-y-6">
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-slate-700">
                    Nome da cidade <span className="text-red-500">*</span>
                  </span>
                  <div className="group relative">
                    <Icon
                      name="building"
                      className="absolute left-4 top-1/2 size-5 -translate-y-1/2 text-slate-400 transition group-focus-within:text-red-500"
                    />
                    <input
                      aria-describedby="city-hint"
                      className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-12 pr-4 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-red-400 focus:bg-white focus:ring-4 focus:ring-red-50"
                      onChange={(event) => setCity(event.target.value)}
                      placeholder="Ex.: São José dos Campos, SP"
                      value={city}
                    />
                  </div>
                  <span id="city-hint" className="mt-2 block text-xs text-slate-400">
                    Inclua a sigla do estado para localizar os dados corretos.
                  </span>
                </label>

                <label className="block">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-700">
                      Conteúdo da pauta{" "}
                      <span className="font-normal text-slate-400">(opcional)</span>
                    </span>
                    <span className="text-xs text-slate-400">{content.length} caracteres</span>
                  </div>
                  <textarea
                    className="min-h-44 w-full resize-y rounded-xl border border-slate-200 bg-slate-50/60 p-4 text-sm leading-relaxed text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-red-400 focus:bg-white focus:ring-4 focus:ring-red-50"
                    onChange={(event) => setContent(event.target.value)}
                    placeholder="Opcional: escreva orientações e observações que devem aparecer no briefing..."
                    value={content}
                  />
                </label>

                <div>
                  <span className="mb-2 block text-sm font-semibold text-slate-700">
                    Logotipo da cidade
                  </span>
                  <div
                    className={`group relative flex min-h-32 cursor-pointer items-center justify-center rounded-xl border-2 border-dashed p-4 text-center transition ${
                      dragging
                        ? "border-red-500 bg-red-50"
                        : file
                          ? "border-emerald-300 bg-emerald-50/50"
                          : "border-slate-200 bg-slate-50/60 hover:border-red-300 hover:bg-red-50/30"
                    }`}
                    onClick={() => fileInput.current?.click()}
                    onDragEnter={() => setDragging(true)}
                    onDragLeave={() => setDragging(false)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={handleDrop}
                  >
                    <input
                      ref={fileInput}
                      accept=".svg,.png,image/svg+xml,image/png"
                      className="hidden"
                      onChange={(event: ChangeEvent<HTMLInputElement>) =>
                        receiveFile(event.target.files?.[0])
                      }
                      type="file"
                    />
                    {file ? (
                      <div className="flex items-center gap-3 text-left">
                        <span className="grid size-11 place-items-center rounded-xl bg-white text-emerald-600 shadow-sm">
                          <Icon name="check" />
                        </span>
                        <div>
                          <div className="max-w-64 truncate text-sm font-semibold text-slate-800">
                            {file.name}
                          </div>
                          <div className="mt-0.5 text-xs text-emerald-600">
                            Arquivo pronto para vetorização
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div>
                        <span className="mx-auto mb-3 grid size-11 place-items-center rounded-xl bg-white text-red-600 shadow-sm ring-1 ring-slate-100 transition group-hover:-translate-y-0.5">
                          <Icon name="upload" />
                        </span>
                        <div className="text-sm font-semibold text-slate-700">
                          Faça upload do logotipo da cidade
                        </div>
                        <div className="mt-1 text-xs text-slate-400">
                          Arraste ou clique para selecionar • SVG ou PNG
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <fieldset>
                  <legend className="mb-3 text-sm font-semibold text-slate-700">
                    Selecionar textura de fundo
                  </legend>
                  <div className="grid grid-cols-3 gap-2.5">
                    {textures.map((option) => (
                      <label
                        key={option.value}
                        className={`relative cursor-pointer overflow-hidden rounded-xl border p-3 transition ${
                          texture === option.value
                            ? "border-red-400 bg-red-50/70 ring-2 ring-red-100"
                            : "border-slate-200 bg-white hover:border-slate-300"
                        }`}
                      >
                        <input
                          checked={texture === option.value}
                          className="sr-only"
                          name="texture"
                          onChange={() => setTexture(option.value)}
                          type="radio"
                        />
                        <span
                          className={`mb-3 block h-8 rounded-lg border border-black/5 texture-${option.value}`}
                        />
                        <span className="block text-xs font-semibold text-slate-700 sm:text-sm">
                          {option.label}
                        </span>
                        <span className="mt-0.5 hidden text-[11px] text-slate-400 sm:block">
                          {option.detail}
                        </span>
                        {texture === option.value && (
                          <span className="absolute right-2 top-2 grid size-5 place-items-center rounded-full bg-red-600 text-white">
                            <Icon name="check" className="size-3" />
                          </span>
                        )}
                      </label>
                    ))}
                  </div>
                </fieldset>

                <button
                  className="group flex h-14 w-full items-center justify-center gap-2.5 rounded-xl bg-red-600 px-6 text-sm font-bold text-white shadow-lg shadow-red-600/20 transition hover:-translate-y-0.5 hover:bg-red-700 hover:shadow-xl hover:shadow-red-600/25 active:translate-y-0 disabled:cursor-wait disabled:translate-y-0 disabled:bg-red-400 disabled:shadow-none"
                  disabled={generationState === "generating"}
                  onClick={renderPdf}
                  type="button"
                >
                  {generationState === "generating" ? (
                    <span className="size-5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  ) : (
                    <Icon
                      name={generationState === "success" ? "download" : "sparkles"}
                      className="size-5 transition group-hover:rotate-6"
                    />
                  )}
                  {generationState === "generating"
                    ? "Gerando pauta..."
                    : generationState === "success"
                      ? "Gerar e baixar novamente"
                      : "Gerar e baixar PDF"}
                </button>
                {generationMessage && (
                  <div
                    aria-live="polite"
                    className={`rounded-xl border px-4 py-3 text-xs leading-relaxed ${
                      generationState === "error"
                        ? "border-red-200 bg-red-50 text-red-700"
                        : generationState === "success"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-slate-200 bg-slate-50 text-slate-600"
                    }`}
                    role={generationState === "error" ? "alert" : "status"}
                  >
                    {generationMessage}
                  </div>
                )}
              </div>
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm xl:sticky xl:top-8">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 sm:px-6">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Pré-visualização</h2>
                  <p className="mt-0.5 text-xs text-slate-400">Formato A4 • Atualização automática</p>
                </div>
                <div className="flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-[11px] font-semibold text-slate-500">
                  <Icon name="file" className="size-3.5" />
                  210 × 297 mm
                </div>
              </div>

              <div className="preview-stage p-5 sm:p-8">
                <article
                  className={`preview-paper texture-${texture} relative mx-auto aspect-[210/297] w-full max-w-[470px] overflow-hidden bg-white shadow-2xl shadow-slate-900/15`}
                >
                  <div className="absolute left-0 top-0 h-full w-2 bg-red-600" />
                  <div className="absolute -right-20 -top-24 size-56 rounded-full border-[42px] border-red-600/5" />
                  <div className="relative flex h-full flex-col px-[9%] py-[10%]">
                    <div className="flex items-start justify-between border-b border-slate-900/10 pb-[7%]">
                      <div className="max-w-[68%]">
                        <div className="mb-2 text-[8px] font-bold uppercase tracking-[0.22em] text-red-600 sm:text-[10px]">
                          Pauta municipal
                        </div>
                        <h3 className="text-lg font-bold leading-tight tracking-tight text-slate-950 sm:text-2xl">
                          {previewTitle}
                        </h3>
                      </div>
                      <div className="grid size-12 place-items-center overflow-hidden rounded-xl border border-red-100 bg-red-50 text-red-600 sm:size-16">
                        {logoUrl ? (
                          <img alt="Logotipo enviado" className="size-full object-contain p-2" src={logoUrl} />
                        ) : (
                          <Icon name="building" className="size-6 sm:size-8" />
                        )}
                      </div>
                    </div>

                    <div className="mt-[9%]">
                      <div className="mb-3 flex items-center gap-2">
                        <span className="h-1 w-8 rounded-full bg-red-600" />
                        <span className="text-[7px] font-bold uppercase tracking-[0.2em] text-slate-400 sm:text-[9px]">
                          Conteúdo oficial
                        </span>
                      </div>
                      <p className="whitespace-pre-line text-[9px] leading-[1.75] text-slate-600 sm:text-[12px]">
                        {previewText}
                      </p>
                    </div>

                    <div className="mt-auto flex items-end justify-between border-t border-slate-900/10 pt-[5%]">
                      <div>
                        <div className="text-[7px] font-bold uppercase tracking-[0.16em] text-slate-400 sm:text-[8px]">
                          Documento gerado por
                        </div>
                        <div className="mt-1 text-[9px] font-bold text-slate-800 sm:text-[11px]">
                          pauta<span className="text-red-600">.</span>pdf
                        </div>
                      </div>
                      <div className="text-[7px] text-slate-400 sm:text-[8px]">
                        Página 01
                      </div>
                    </div>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
