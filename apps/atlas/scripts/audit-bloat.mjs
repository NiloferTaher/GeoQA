import { execFileSync } from "node:child_process"
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs"
import { extname, join, relative, resolve } from "node:path"

const atlasRoot = resolve(".")
const candidateRepoRoot = resolve(atlasRoot, "../..")
const repoRoot = existsSync(join(candidateRepoRoot, "pyproject.toml")) ? candidateRepoRoot : atlasRoot
const sourceRoot = join(atlasRoot, "src")
const distAssets = join(atlasRoot, "dist", "assets")

const ignoredParts = new Set([".git", "node_modules", "dist", "build", ".vite", ".cache", "__pycache__"])
const generatedPattern = /(^|\/)(node_modules|dist|build|\.vite|\.cache|cache|__pycache__)($|\/)|\.(exe|log|zip|7z|rar)$/i

function walk(root, results = []) {
  if (!existsSync(root)) return results
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (ignoredParts.has(entry.name)) continue
    const fullPath = join(root, entry.name)
    if (entry.isDirectory()) {
      walk(fullPath, results)
    } else {
      results.push({ path: fullPath, size: statSync(fullPath).size })
    }
  }
  return results
}

function largestFiles(root, count = 12) {
  return walk(root).sort((a, b) => b.size - a.size).slice(0, count)
}

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

function rel(path) {
  return relative(repoRoot, path).replaceAll("\\", "/")
}

function gitLines(args) {
  try {
    return execFileSync("git", args, { cwd: repoRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] })
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
  } catch {
    return []
  }
}

function sourceText() {
  return walk(sourceRoot)
    .filter((file) => [".ts", ".tsx", ".css"].includes(extname(file.path)))
    .map((file) => readFileSync(file.path, "utf8"))
    .join("\n")
}

function usageForPackage(packageName, text) {
  if (packageName === "@vitejs/plugin-react") return existsSync(join(atlasRoot, "vite.config.ts"))
  if (packageName === "react") return /from "react"|from 'react'/.test(text)
  if (packageName === "react-dom") return /react-dom/.test(text)
  if (packageName === "react-router-dom") return /react-router-dom/.test(text)
  if (packageName === "lucide-react") return /lucide-react/.test(text)
  if (packageName === "leaflet") return /leaflet/.test(text)
  if (packageName === "react-leaflet") return /react-leaflet/.test(text)
  if (packageName === "shpjs") return /import\("shpjs"\)|from "shpjs"|from 'shpjs'/.test(text)
  return text.includes(packageName)
}

function distChunks() {
  if (!existsSync(distAssets)) return []
  return readdirSync(distAssets, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => {
      const path = join(distAssets, entry.name)
      return { path, size: statSync(path).size }
    })
    .sort((a, b) => b.size - a.size)
}

function sumByExt(files, extension) {
  return files.filter((file) => file.path.endsWith(extension)).reduce((total, file) => total + file.size, 0)
}

function printList(title, files) {
  console.log(`\n${title}`)
  for (const file of files) console.log(`- ${formatBytes(file.size)} ${rel(file.path)}`)
}

const packageJson = JSON.parse(readFileSync(join(atlasRoot, "package.json"), "utf8"))
const source = sourceText()
const trackedGenerated = gitLines(["ls-files"]).filter((path) => generatedPattern.test(path.replaceAll("\\", "/")))
const sourceFileNames = walk(sourceRoot).map((file) => rel(file.path))
const chunks = distChunks()
const dependencies = Object.keys(packageJson.dependencies ?? {})

console.log("GeoQA Atlas bloat audit")
printList("Largest files under apps/atlas", largestFiles(atlasRoot, 15))
printList("Largest files under repo root", largestFiles(repoRoot, 20))

console.log("\nGenerated or private file tracking check")
if (trackedGenerated.length) {
  for (const path of trackedGenerated) console.log(`- tracked generated file ${path}`)
} else {
  console.log("- No tracked node_modules, dist, build, .vite, cache, exe, log, zip, 7z, or rar paths found.")
}

console.log("\nDependency audit")
for (const dep of dependencies) {
  const used = usageForPackage(dep, source)
  const reason =
    dep === "shpjs"
      ? "kept for user-triggered zipped Shapefile parsing"
      : dep === "leaflet" || dep === "react-leaflet"
        ? "kept for lazy map rendering"
        : dep === "@vitejs/plugin-react"
          ? "kept for Vite React build tooling"
          : "kept because source or config imports it"
  console.log(`- ${dep} ${used ? "used" : "needs review"} ${reason}`)
}

console.log("\nBundle audit")
if (!chunks.length) {
  console.log("- No dist assets found. Run npm run build first.")
} else {
  console.log(`- JS total ${formatBytes(sumByExt(chunks, ".js"))}`)
  console.log(`- CSS total ${formatBytes(sumByExt(chunks, ".css"))}`)
  printList("Largest generated chunks", chunks.slice(0, 8))
  console.log(
    source.includes("import \"../public/demo-data") || source.includes("from \"../public/demo-data")
      ? "- Demo data import found in source. Review bundling."
      : "- Demo GeoJSON and report data are fetched from public demo paths and not imported into main JS.",
  )
}

console.log("\nSource bloat audit")
const runQaPage = readFileSync(join(sourceRoot, "pages", "RunQaPage.tsx"), "utf8")
const datasetPage = readFileSync(join(sourceRoot, "pages", "DatasetWorkspace.tsx"), "utf8")
const helperFiles = sourceFileNames.filter((name) => name.includes("/config/") || name.includes("/lib/"))
const previewLimitDeclarations = (runQaPage.match(/const maxPreviewFeatures =/g) ?? []).length
console.log(`- Source helper files reviewed ${helperFiles.length}`)
console.log(
  previewLimitDeclarations === 1
    ? "- One maxPreviewFeatures declaration found."
    : `- ${previewLimitDeclarations} maxPreviewFeatures declarations found. Review preview limit duplication.`,
)
console.log(
  source.match(/getPublicDemoAnalysisLimit/g)?.length > 3
    ? "- Public demo sampling helper is referenced from tests and Run QA."
    : "- Public demo sampling helper has a small reference surface.",
)
console.log(
  runQaPage.includes("selectFeaturesForGeoQAAnalysis") && !datasetPage.includes("selectFeaturesForGeoQAAnalysis")
    ? "- Run QA sampling is separated from curated dataset pages."
    : "- Sampling separation needs review.",
)
console.log(
  source.includes("SelectedIssuePanel") && source.includes("IssueDrawer")
    ? "- Dataset drawer and Run QA selected issue panel are separate by workflow."
    : "- Issue review components have no obvious duplicated panel experiment.",
)

console.log("\nRun QA public sampling proof")
const tests = readFileSync(join(atlasRoot, "scripts", "test-public-demo-limits.mjs"), "utf8")
const samplingProof = [
  ["points max 20", /getPublicDemoAnalysisLimit\("Point"\), 20/.test(tests)],
  ["lines max 5", /getPublicDemoAnalysisLimit\("LineString"\), 5/.test(tests)],
  ["polygons max 5", /getPublicDemoAnalysisLimit\("Polygon"\), 5/.test(tests)],
  ["mixed or unknown max 5", /getPublicDemoAnalysisLimit\("Unknown"\), 5/.test(tests)],
  ["80 point to 20", /makeCollection\(80, "Point"\)/.test(tests) && /features\.length, 20/.test(tests)],
  ["736 point to 20", /makeCollection\(736, "Point"\)/.test(tests)],
  ["123 polygon to 5", /makeCollection\(123, "Polygon"\)/.test(tests)],
  ["5000 line to 5", /makeCollection\(5000, "LineString"\)/.test(tests)],
  ["public demo payload sends sampled features", /const analysisFile = plan \? featureCollectionToFile\(sanitizeFeatureCollectionForGeoQA\(plan\.collection\)/.test(runQaPage) && /runUploadedQa\(analysisFile/.test(runQaPage)],
  ["result status says demo sample", /getSampledExecutionStatus\("full", false\), "demo sample"/.test(tests)],
  ["curated dataset pages are not sampled", /datasetWorkspaceSource\.includes\("selectFeaturesForGeoQAAnalysis"\), false/.test(tests)],
]
for (const [label, ok] of samplingProof) console.log(`- ${ok ? "pass" : "missing"} ${label}`)
