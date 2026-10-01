import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Divider,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  Select,
  SimpleGrid,
  Spinner,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { FiRefreshCw, FiShare2 } from "react-icons/fi";
import { useParams } from "react-router-dom";
import {
  getExportUrl,
  getMediaJob,
  getProjectExports,
  getSocialOptions,
  startSocialExport,
  type ExportFile,
  type MediaJob,
  type ProjectExports,
  type SocialOptions,
} from "../api/workflows";

function formatSize(size: number) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function ExportSection({
  title,
  description,
  files,
  projectId,
  social = false,
}: {
  title: string;
  description: string;
  files: ExportFile[];
  projectId: string;
  social?: boolean;
}) {
  return (
    <Stack align="stretch" spacing={4}>
      <Box>
        <Heading size="md">{title}</Heading>
        <Text color="gray.600">{description}</Text>
      </Box>
      {!files.length ? <Text color="gray.600">No {social ? "social exports" : "renders"} yet.</Text> : <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={4}>
        {files.map(file => <Box key={file.filename} borderWidth="1px" borderColor="gray.200" borderRadius="md" bg="white" overflow="hidden">
          <video controls preload="none" src={getExportUrl(projectId, file.filename, social)} style={{ display: "block", width: "100%", maxHeight: 360, background: "#111" }} />
          <Stack p={4} spacing={1}>
            <Text fontWeight="semibold" overflowWrap="anywhere">{file.filename}</Text>
            <Text fontSize="sm" color="gray.600">{formatSize(file.size_bytes)} · {new Date(file.modified_at).toLocaleString()}</Text>
          </Stack>
        </Box>)}
      </SimpleGrid>}
    </Stack>
  );
}

export function ExportsPage() {
  const { projectId } = useParams();
  const activeProjectId = projectId ?? "";
  const [exports, setExports] = useState<ProjectExports>({ renders: [], social_exports: [] });
  const [options, setOptions] = useState<SocialOptions>({ presets: [], framing_modes: [] });
  const [sourceFilename, setSourceFilename] = useState("");
  const [preset, setPreset] = useState("");
  const [framing, setFraming] = useState<"crop" | "fit">("crop");
  const [job, setJob] = useState<MediaJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const jobId = job?.job_id;
  const jobStatus = job?.status;

  async function refreshExports() {
    const result = await getProjectExports(activeProjectId);
    setExports(result);
    setSourceFilename(current => result.renders.some(item => item.filename === current) ? current : result.renders[0]?.filename ?? "");
  }

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    Promise.all([
      getProjectExports(activeProjectId, controller.signal),
      getSocialOptions(activeProjectId, controller.signal),
    ]).then(([fileList, socialOptions]) => {
      if (!active) return;
      setExports(fileList);
      setOptions(socialOptions);
      setSourceFilename(fileList.renders[0]?.filename ?? "");
      setPreset(socialOptions.presets[0]?.key ?? "");
    }).catch(reason => {
      if (active && !controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load exports.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [activeProjectId]);

  useEffect(() => {
    if (!jobId || !jobStatus || !["queued", "running"].includes(jobStatus)) return;
    let active = true;
    const poll = async () => {
      try {
        const updated = await getMediaJob(activeProjectId, jobId);
        if (!active) return;
        setJob(updated);
        if (updated.status === "completed") {
          const fileList = await getProjectExports(activeProjectId);
          if (active) {
            setExports(fileList);
            setSourceFilename(current => fileList.renders.some(item => item.filename === current) ? current : fileList.renders[0]?.filename ?? "");
          }
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Could not check export status.");
      }
    };
    const timer = window.setInterval(() => { void poll(); }, 1200);
    void poll();
    return () => { active = false; window.clearInterval(timer); };
  }, [activeProjectId, jobId, jobStatus]);

  async function handleRefresh() {
    setRefreshing(true);
    setError("");
    try { await refreshExports(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not refresh exports."); }
    finally { setRefreshing(false); }
  }

  async function handleSocialExport() {
    if (!sourceFilename || !preset || job && ["queued", "running"].includes(job.status)) return;
    setError("");
    try { setJob(await startSocialExport(activeProjectId, sourceFilename, preset, framing)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start social export."); }
  }

  if (loading) return <HStack role="status"><Spinner /><Text>Loading exports…</Text></HStack>;
  const running = Boolean(job && ["queued", "running"].includes(job.status));

  return (
    <VStack align="stretch" spacing={6}>
      <HStack justify="space-between" align="start" flexWrap="wrap">
        <Box><Heading size="lg">Exports</Heading><Text color="gray.600">Completed videos saved in this project.</Text></Box>
        <Button leftIcon={<FiRefreshCw />} onClick={() => void handleRefresh()} isLoading={refreshing}>Refresh</Button>
      </HStack>
      {error && <Alert status="error"><AlertIcon />{error}</Alert>}
      <ExportSection title="Normal renders" description="Rendered edits in the configured exports directory." files={exports.renders} projectId={activeProjectId} />
      <Divider />
      <Stack align="stretch" spacing={4}>
        <Box><Heading size="md">Create social export</Heading><Text color="gray.600">Convert a normal render using a supported social format.</Text></Box>
        {!exports.renders.length ? <Text color="gray.600">A normal render is required before social conversion.</Text> : <HStack align="end" spacing={3} flexWrap="wrap">
          <FormControl maxW="360px"><FormLabel>Source render</FormLabel><Select value={sourceFilename} onChange={event => setSourceFilename(event.target.value)} isDisabled={running}>{exports.renders.map(file => <option key={file.filename} value={file.filename}>{file.filename}</option>)}</Select></FormControl>
          <FormControl maxW="280px"><FormLabel>Format</FormLabel><Select value={preset} onChange={event => setPreset(event.target.value)} isDisabled={running}>{options.presets.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}</Select></FormControl>
          <FormControl maxW="240px"><FormLabel>Framing</FormLabel><Select value={framing} onChange={event => setFraming(event.target.value as "crop" | "fit")} isDisabled={running}>{options.framing_modes.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}</Select></FormControl>
          <Button leftIcon={<FiShare2 />} colorScheme="blue" onClick={() => void handleSocialExport()} isDisabled={!sourceFilename || !preset || running} isLoading={running}>Create social export</Button>
        </HStack>}
        {job && <Alert status={job.status === "failed" ? "error" : job.status === "completed" ? "success" : "info"}>
          <AlertIcon />
          <VStack align="start" spacing={1}>
            <Text fontWeight="semibold">{job.status === "queued" ? "Conversion queued" : job.status === "running" ? "Converting…" : job.status === "completed" ? "Social export complete" : "Social export failed"}</Text>
            {job.status === "failed" && <Text>{job.error}</Text>}
            {job.status === "completed" && job.output_filename && <Text>{job.output_filename}</Text>}
            {running && <Text fontSize="sm">This operation continues in the local application process.</Text>}
          </VStack>
        </Alert>}
      </Stack>
      <Divider />
      <ExportSection title="Social exports" description="Vertical derivatives in the configured social exports directory." files={exports.social_exports} projectId={activeProjectId} social />
    </VStack>
  );
}
