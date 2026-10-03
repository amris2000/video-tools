import {
  Alert,
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertIcon,
  AspectRatio,
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
import { FiRefreshCw, FiShare2, FiTrash2 } from "react-icons/fi";
import { useParams } from "react-router-dom";
import {
  deleteExportFile,
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
import { FiPlayCircle } from "react-icons/fi";
import { VideoPreviewModal } from "../components/media/VideoPreviewModal";
import { useRef } from "react";

function formatSize(size: number) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function ExportSection({
  title,
  description,
  files,
  social = false,
  onSelect,
  onDelete,
  deleting,
}: {
  title: string;
  description: string;
  files: ExportFile[];
  social?: boolean;
  onSelect: (file: ExportFile, social: boolean) => void;
  onDelete: (file: ExportFile, social: boolean) => void;
  deleting: string | null;
}) {
  return (
    <Stack align="stretch" spacing={4}>
      <Box>
        <Heading size="md">{title}</Heading>
        <Text color="gray.600">{description}</Text>
      </Box>
      {!files.length ? (
        <Text color="gray.600">
          No {social ? "social exports" : "renders"} yet.
        </Text>
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, xl: 3 }} spacing={4}>
          {files.map((file) => (
            <Box
              key={file.filename}
              bg="white"
              borderWidth="1px"
              borderColor="gray.200"
              borderRadius="md"
              overflow="hidden"
              _hover={{ borderColor: "blue.400", transform: "translateY(-1px)" }}
            >
              <Button
                type="button"
                display="block"
                width="100%"
                height="auto"
                p={0}
                whiteSpace="normal"
                textAlign="left"
                bg="transparent"
                borderRadius="0"
                onClick={() => onSelect(file, social)}
                _hover={{ bg: "transparent" }}
                _active={{ bg: "transparent" }}
              >
                <AspectRatio ratio={16 / 10} bg="gray.900">
                  <Stack
                    color="white"
                    align="center"
                    justify="center"
                    spacing={2}
                  >
                    <FiPlayCircle size={34} />
                    <Text fontSize="sm">
                      Preview {social ? "social export" : "render"}
                    </Text>
                  </Stack>
                </AspectRatio>
              </Button>
              <Stack p={3} spacing={1} align="stretch">
                <Text
                  fontSize="sm"
                  fontWeight="semibold"
                  overflowWrap="anywhere"
                  noOfLines={2}
                >
                  {file.filename}
                </Text>
                <Text fontSize="xs" color="gray.600">
                  {formatSize(file.size_bytes)} ·{" "}
                  {new Date(file.modified_at).toLocaleString()}
                </Text>
                <HStack justify="flex-end" pt={1}>
                  <Button
                    size="xs"
                    colorScheme="red"
                    variant="ghost"
                    leftIcon={<FiTrash2 />}
                    onClick={() => onDelete(file, social)}
                    isLoading={deleting === `${social ? "social" : "render"}:${file.filename}`}
                  >
                    Delete
                  </Button>
                </HStack>
              </Stack>
            </Box>
          ))}
        </SimpleGrid>
      )}
    </Stack>
  );
}

export function ExportsPage() {
  const { projectId } = useParams();
  const activeProjectId = projectId ?? "";
  const [viewMode, setViewMode] = useState<"renders" | "social">("renders");
  const [exports, setExports] = useState<ProjectExports>({
    renders: [],
    social_exports: [],
  });
  const [options, setOptions] = useState<SocialOptions>({
    presets: [],
    framing_modes: [],
  });
  const [sourceFilename, setSourceFilename] = useState("");
  const [preset, setPreset] = useState("");
  const [framing, setFraming] = useState<"crop" | "fit">("crop");
  const [job, setJob] = useState<MediaJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{
    file: ExportFile;
    social: boolean;
  } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{
    file: ExportFile;
    social: boolean;
  } | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const cancelDeleteRef = useRef<HTMLButtonElement>(null);
  const jobId = job?.job_id;
  const jobStatus = job?.status;

  async function refreshExports() {
    const result = await getProjectExports(activeProjectId);
    setExports(result);
    setSourceFilename((current) =>
      result.renders.some((item) => item.filename === current)
        ? current
        : (result.renders[0]?.filename ?? ""),
    );
  }

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    Promise.all([
      getProjectExports(activeProjectId, controller.signal),
      getSocialOptions(activeProjectId, controller.signal),
    ])
      .then(([fileList, socialOptions]) => {
        if (!active) return;
        setExports(fileList);
        setOptions(socialOptions);
        setSourceFilename(fileList.renders[0]?.filename ?? "");
        setPreset(socialOptions.presets[0]?.key ?? "");
      })
      .catch((reason) => {
        if (active && !controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load exports.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [activeProjectId]);

  useEffect(() => {
    if (!jobId || !jobStatus || !["queued", "running"].includes(jobStatus))
      return;
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
            setViewMode("social");
            if (updated.output_filename) {
              const created = fileList.social_exports.find(
                (item) => item.filename === updated.output_filename,
              );
              if (created) {
                setPreview({ file: created, social: true });
              }
            }
            setSourceFilename((current) =>
              fileList.renders.some((item) => item.filename === current)
                ? current
                : (fileList.renders[0]?.filename ?? ""),
            );
          }
        }
      } catch (reason) {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not check export status.",
          );
      }
    };
    const timer = window.setInterval(() => {
      void poll();
    }, 1200);
    void poll();
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeProjectId, jobId, jobStatus]);

  async function handleRefresh() {
    setRefreshing(true);
    setError("");
    try {
      await refreshExports();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not refresh exports.",
      );
    } finally {
      setRefreshing(false);
    }
  }

  async function handleSocialExport() {
    if (
      !sourceFilename ||
      !preset ||
      (job && ["queued", "running"].includes(job.status))
    )
      return;
    setError("");
    try {
      setJob(
        await startSocialExport(
          activeProjectId,
          sourceFilename,
          preset,
          framing,
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not start social export.",
      );
    }
  }

  async function handleDeleteExport() {
    if (!pendingDelete) return;
    const key = `${pendingDelete.social ? "social" : "render"}:${pendingDelete.file.filename}`;
    setDeletingKey(key);
    setError("");
    try {
      await deleteExportFile(
        activeProjectId,
        pendingDelete.file.filename,
        pendingDelete.social,
      );
      if (
        preview &&
        preview.file.filename === pendingDelete.file.filename &&
        preview.social === pendingDelete.social
      ) {
        setPreview(null);
      }
      setPendingDelete(null);
      await refreshExports();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not delete export.",
      );
    } finally {
      setDeletingKey(null);
    }
  }

  if (loading)
    return (
      <HStack role="status">
        <Spinner />
        <Text>Loading exports…</Text>
      </HStack>
    );
  const running = Boolean(job && ["queued", "running"].includes(job.status));

  return (
    <VStack align="stretch" spacing={6}>
      <HStack justify="space-between" align="start" flexWrap="wrap">
        <Box>
          <Heading size="lg">Exports</Heading>
          <Text color="gray.600">Completed videos saved in this project.</Text>
        </Box>
        <Button
          leftIcon={<FiRefreshCw />}
          onClick={() => void handleRefresh()}
          isLoading={refreshing}
        >
          Refresh
        </Button>
      </HStack>
      {error && (
        <Alert status="error">
          <AlertIcon />
          {error}
        </Alert>
      )}
      <HStack spacing={2}>
        <Button
          variant={viewMode === "renders" ? "solid" : "outline"}
          colorScheme={viewMode === "renders" ? "blue" : undefined}
          onClick={() => setViewMode("renders")}
        >
          Renders
        </Button>
        <Button
          variant={viewMode === "social" ? "solid" : "outline"}
          colorScheme={viewMode === "social" ? "blue" : undefined}
          onClick={() => setViewMode("social")}
        >
          Social exports
        </Button>
      </HStack>

      {viewMode === "renders" ? (
        <ExportSection
          title="Normal renders"
          description="Rendered edits in the configured exports directory."
          files={exports.renders}
          onSelect={(file, social) => setPreview({ file, social })}
          onDelete={(file, social) => setPendingDelete({ file, social })}
          deleting={deletingKey}
        />
      ) : (
        <>
          <Stack align="stretch" spacing={4}>
            <Box>
              <Heading size="md">Create social export</Heading>
              <Text color="gray.600">
                Convert a normal render using a supported social format.
              </Text>
            </Box>
            {!exports.renders.length ? (
              <Text color="gray.600">
                A normal render is required before social conversion.
              </Text>
            ) : (
              <HStack align="end" spacing={3} flexWrap="wrap">
                <FormControl maxW="360px">
                  <FormLabel>Source render</FormLabel>
                  <Select
                    value={sourceFilename}
                    onChange={(event) => setSourceFilename(event.target.value)}
                    isDisabled={running}
                  >
                    {exports.renders.map((file) => (
                      <option key={file.filename} value={file.filename}>
                        {file.filename}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <FormControl maxW="280px">
                  <FormLabel>Format</FormLabel>
                  <Select
                    value={preset}
                    onChange={(event) => setPreset(event.target.value)}
                    isDisabled={running}
                  >
                    {options.presets.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <FormControl maxW="240px">
                  <FormLabel>Framing</FormLabel>
                  <Select
                    value={framing}
                    onChange={(event) =>
                      setFraming(event.target.value as "crop" | "fit")
                    }
                    isDisabled={running}
                  >
                    {options.framing_modes.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  leftIcon={<FiShare2 />}
                  colorScheme="blue"
                  onClick={() => void handleSocialExport()}
                  isDisabled={!sourceFilename || !preset || running}
                  isLoading={running}
                >
                  Create social export
                </Button>
              </HStack>
            )}
            {job && (
              <Alert
                status={
                  job.status === "failed"
                    ? "error"
                    : job.status === "completed"
                      ? "success"
                      : "info"
                }
              >
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontWeight="semibold">
                    {job.status === "queued"
                      ? "Conversion queued"
                      : job.status === "running"
                        ? "Converting…"
                        : job.status === "completed"
                          ? "Social export complete"
                          : "Social export failed"}
                  </Text>
                  {job.status === "failed" && <Text>{job.error}</Text>}
                  {job.status === "completed" && job.output_filename && (
                    <Text>{job.output_filename}</Text>
                  )}
                  {running && (
                    <Text fontSize="sm">
                      This operation continues in the local application process.
                    </Text>
                  )}
                </VStack>
              </Alert>
            )}
          </Stack>
          <Divider />
          <ExportSection
            title="Social exports"
            description="Vertical derivatives in the configured social exports directory."
            files={exports.social_exports}
            social
            onSelect={(file, social) => setPreview({ file, social })}
            onDelete={(file, social) => setPendingDelete({ file, social })}
            deleting={deletingKey}
          />
        </>
      )}
      <VideoPreviewModal
        isOpen={preview !== null}
        onClose={() => setPreview(null)}
        title={preview?.file.filename ?? "Export preview"}
        videoUrl={
          preview
            ? getExportUrl(
                activeProjectId,
                preview.file.filename,
                preview.social,
              )
            : ""
        }
        metadata={
          preview && (
            <>
              <Text fontWeight="semibold">
                {preview.social ? "Social export" : "Normal render"}
              </Text>
              <Text color="gray.600">
                {formatSize(preview.file.size_bytes)}
              </Text>
              <Text color="gray.600">
                {new Date(preview.file.modified_at).toLocaleString()}
              </Text>
            </>
          )
        }
      />

      <AlertDialog
        isOpen={pendingDelete !== null}
        leastDestructiveRef={cancelDeleteRef}
        onClose={() => {
          if (!deletingKey) setPendingDelete(null);
        }}
        isCentered
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete export
            </AlertDialogHeader>
            <AlertDialogBody>
              This will permanently delete
              {" "}
              <Text as="span" fontWeight="semibold" overflowWrap="anywhere">
                {pendingDelete?.file.filename}
              </Text>
              {" "}
              from this project. Continue?
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button
                ref={cancelDeleteRef}
                onClick={() => setPendingDelete(null)}
                isDisabled={Boolean(deletingKey)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="red"
                ml={3}
                onClick={() => void handleDeleteExport()}
                isLoading={Boolean(deletingKey)}
              >
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </VStack>
  );
}
