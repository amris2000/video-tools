import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Checkbox,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  Input,
  Spinner,
  Stack,
  Table,
  TableContainer,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import {
  getDetectedImportSources,
  getMediaJob,
  importGoProFiles,
  scanGoProImport,
  type DetectedImportSource,
  type ImportPlan,
  type ImportResult,
  type MediaJob,
} from "../api/workflows";

function formatSize(size: number) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

const statusLabels = {
  new: "New",
  already_imported: "Already imported",
  conflict: "Conflict",
} as const;

const stageLabels = {
  import: "Importing",
  organize: "Organizing",
  thumbnails: "Thumbnails",
  probe: "Probing",
} as const;

function selectablePaths(plan: ImportPlan) {
  return plan.files
    .filter((file) => file.status !== "conflict")
    .map((file) => file.source_relative_path);
}

export function ImportPage() {
  const { projectId } = useParams();
  const activeProjectId = projectId ?? "";
  const [sourcePath, setSourcePath] = useState("");
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [job, setJob] = useState<MediaJob | null>(null);
  const [busy, setBusy] = useState<"scan" | "import" | null>(null);
  const [error, setError] = useState("");
  const [detectedSources, setDetectedSources] = useState<
    DetectedImportSource[]
  >([]);
  const [detecting, setDetecting] = useState(true);
  const [detectionError, setDetectionError] = useState("");
  const handledJobId = useRef("");
  const jobId = job?.job_id;
  const jobStatus = job?.status;

  useEffect(() => {
    let active = true;
    getDetectedImportSources()
      .then(
        (sources) => {
          if (active) setDetectedSources(sources);
        },
        (reason) => {
          if (active)
            setDetectionError(
              reason instanceof Error
                ? reason.message
                : "Could not detect removable sources.",
            );
        },
      )
      .finally(() => {
        if (active) setDetecting(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!jobId || !jobStatus || !["queued", "running"].includes(jobStatus))
      return;
    let active = true;
    let polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const latest = await getMediaJob(activeProjectId, jobId);
        if (active) setJob(latest);
      } catch (reason) {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not check import progress.",
          );
      } finally {
        polling = false;
      }
    };
    const timer = window.setInterval(() => {
      void poll();
    }, 700);
    void poll();
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeProjectId, jobId, jobStatus]);

  useEffect(() => {
    if (
      job?.status !== "completed" ||
      !job.result ||
      handledJobId.current === job.job_id
    )
      return;
    handledJobId.current = job.job_id;
    const source = plan?.source;
    if (!source) return;
    let active = true;
    scanGoProImport(activeProjectId, source)
      .then((refreshedPlan) => {
        if (!active) return;
        setPlan(refreshedPlan);
        setSelectedPaths(new Set(selectablePaths(refreshedPlan)));
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Import completed, but the plan could not be refreshed.",
          );
      });
    return () => {
      active = false;
    };
  }, [activeProjectId, job?.job_id, job?.status, job?.result, plan?.source]);

  async function refreshDevices() {
    setDetecting(true);
    setDetectionError("");
    try {
      setDetectedSources(await getDetectedImportSources());
    } catch (reason) {
      setDetectionError(
        reason instanceof Error
          ? reason.message
          : "Could not detect removable sources.",
      );
    } finally {
      setDetecting(false);
    }
  }

  async function scanPath(path: string) {
    if (!path.trim()) return;
    setBusy("scan");
    setError("");
    setJob(null);
    try {
      const nextPlan = await scanGoProImport(activeProjectId, path.trim());
      setPlan(nextPlan);
      setSourcePath(nextPlan.source);
      setSelectedPaths(new Set(selectablePaths(nextPlan)));
    } catch (reason) {
      setPlan(null);
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not scan this GoPro source.",
      );
    } finally {
      setBusy(null);
    }
  }

  function handleScan(event: FormEvent) {
    event.preventDefault();
    void scanPath(sourcePath);
  }

  async function handleImport() {
    if (!plan || selectedPaths.size === 0) return;
    setBusy("import");
    setError("");
    try {
      setJob(
        await importGoProFiles(activeProjectId, plan.source, [
          ...selectedPaths,
        ]),
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not start import.",
      );
    } finally {
      setBusy(null);
    }
  }

  function updateSelection(path: string, checked: boolean) {
    setSelectedPaths((current) => {
      const next = new Set(current);
      if (checked) next.add(path);
      else next.delete(path);
      return next;
    });
  }

  function selectAllNew() {
    setSelectedPaths(
      new Set(
        plan?.files
          .filter((file) => file.status === "new")
          .map((file) => file.source_relative_path) ?? [],
      ),
    );
  }

  function selectAllAvailable() {
    setSelectedPaths(new Set(plan ? selectablePaths(plan) : []));
  }

  const isJobActive = job?.status === "queued" || job?.status === "running";
  const result = job?.result as ImportResult | undefined;
  const stages = job?.progress?.stages;

  return (
    <VStack align="stretch" spacing={5}>
      <Box>
        <Heading size="lg">Import</Heading>
        <Text color="gray.600">
          Import missing video files and complete local thumbnails and metadata.
        </Text>
      </Box>

      <Stack align="stretch" spacing={3}>
        <HStack justify="space-between" flexWrap="wrap">
          <Heading size="md">Detected GoPro sources</Heading>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void refreshDevices()}
            isLoading={detecting}
          >
            Detect GoPro
          </Button>
        </HStack>
        {detectionError && (
          <Alert status="warning">
            <AlertIcon />
            {detectionError}
          </Alert>
        )}
        {detecting && (
          <HStack role="status">
            <Spinner size="sm" />
            <Text>Checking removable media…</Text>
          </HStack>
        )}
        {!detecting && !detectionError && !detectedSources.length && (
          <Text color="gray.600">
            No GoPro media detected. Connect a GoPro/SD card and choose Detect
            GoPro, or enter a source folder below.
          </Text>
        )}
        {detectedSources.map((source) => (
          <HStack
            key={source.path}
            justify="space-between"
            borderWidth="1px"
            borderColor="gray.200"
            borderRadius="md"
            bg="white"
            px={3}
            py={2}
            flexWrap="wrap"
          >
            <Box minWidth={0}>
              <Text fontWeight="semibold">{source.label}</Text>
              <Text fontSize="sm" color="gray.600" overflowWrap="anywhere">
                {source.path}
              </Text>
            </Box>
            <Button
              size="sm"
              colorScheme="blue"
              onClick={() => {
                setSourcePath(source.path);
                void scanPath(source.path);
              }}
              isDisabled={busy !== null || isJobActive}
            >
              Use
            </Button>
          </HStack>
        ))}
      </Stack>

      {error && (
        <Alert status="error">
          <AlertIcon />
          {error}
        </Alert>
      )}
      {result && (
        <Alert status={result.errors.length ? "warning" : "success"}>
          <AlertIcon />
          <VStack align="start" spacing={1}>
            <Text>
              {result.everything_up_to_date
                ? "Everything is up to date."
                : `Imported ${result.imported}; skipped ${result.skipped}; conflicts ${result.conflicts}.`}
            </Text>
            {result.errors.map((message, index) => (
              <Text key={`${index}-${message}`} fontSize="sm">
                {message}
              </Text>
            ))}
          </VStack>
        </Alert>
      )}

      <Box as="form" onSubmit={handleScan}>
        <HStack align="end" spacing={3} flexWrap="wrap">
          <FormControl maxW="760px">
            <FormLabel>GoPro source folder or connected camera</FormLabel>
            <Input
              value={sourcePath}
              onChange={(event) => {
                setSourcePath(event.target.value);
                setPlan(null);
                setJob(null);
                setSelectedPaths(new Set());
              }}
              placeholder="C:\\DCIM, /media/card/DCIM, or detected camera"
              isDisabled={isJobActive}
            />
          </FormControl>
          <Button
            type="submit"
            colorScheme="blue"
            isLoading={busy === "scan"}
            isDisabled={!sourcePath.trim() || busy !== null || isJobActive}
          >
            Scan folder
          </Button>
        </HStack>
      </Box>

      {busy === "scan" && (
        <HStack role="status">
          <Spinner size="sm" />
          <Text>Scanning source videos…</Text>
        </HStack>
      )}

      {job && (
        <Box
          borderWidth="1px"
          borderColor="gray.200"
          borderRadius="md"
          bg="white"
          p={3}
        >
          <Stack spacing={2}>
            <Text fontWeight="semibold">
              {job.status === "queued"
                ? "Import pipeline queued"
                : job.status === "running"
                  ? "Processing selected clips…"
                  : job.status === "failed"
                    ? "Import pipeline failed"
                    : result?.everything_up_to_date
                      ? "Everything is up to date."
                      : "Import pipeline complete"}
            </Text>
            {(["import", "organize", "thumbnails", "probe"] as const).map(
              (name) => {
                const stage = stages?.[name] ?? {
                  status: "waiting" as const,
                  current_file: null,
                  completed: 0,
                  total: 0,
                  errors: [],
                };
                const stateText =
                  stage.status === "running"
                    ? stage.current_file || "Starting…"
                    : stage.status === "failed"
                      ? "Completed with errors"
                      : stage.status === "completed"
                        ? stage.total === 0
                          ? "DONE · 0 needed"
                          : "DONE"
                        : "Waiting…";
                return (
                  <Stack key={name} spacing={0}>
                    <HStack justify="space-between" spacing={4}>
                      <Text fontSize="sm" fontWeight="medium">
                        {stageLabels[name]}
                      </Text>
                      <Text
                        fontSize="sm"
                        color={
                          stage.status === "failed" ? "red.600" : "gray.700"
                        }
                        textAlign="right"
                      >
                        {stateText} · {stage.completed} / {stage.total}
                      </Text>
                    </HStack>
                    {stage.errors.map((message, index) => (
                      <Text
                        key={`${index}-${message}`}
                        fontSize="xs"
                        color="red.600"
                      >
                        {message}
                      </Text>
                    ))}
                  </Stack>
                );
              },
            )}
            {job.status === "failed" && job.error && (
              <Text fontSize="sm" color="red.600">
                {job.error}
              </Text>
            )}
          </Stack>
        </Box>
      )}

      {plan && (
        <>
          <HStack spacing={5} flexWrap="wrap" aria-label="Import scan summary">
            <Text fontWeight="semibold">
              {plan.total_source_files} source videos
            </Text>
            <Text color="green.700">{plan.new_files} new</Text>
            <Text color="gray.600">
              {plan.already_imported} already imported
            </Text>
            <Text color={plan.conflicts ? "orange.700" : "gray.600"}>
              {plan.conflicts} conflicts
            </Text>
          </HStack>
          <HStack justify="space-between" flexWrap="wrap">
            <HStack>
              <Button
                size="sm"
                onClick={selectAllNew}
                isDisabled={!plan.new_files || busy !== null || isJobActive}
              >
                Select all new
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={selectAllAvailable}
                isDisabled={busy !== null || isJobActive}
              >
                Select all available
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectedPaths(new Set())}
                isDisabled={!selectedPaths.size || busy !== null || isJobActive}
              >
                Select none
              </Button>
            </HStack>
            <Button
              colorScheme="blue"
              onClick={() => void handleImport()}
              isLoading={busy === "import" || isJobActive}
              isDisabled={!selectedPaths.size || busy !== null || isJobActive}
            >
              Import selected ({selectedPaths.size})
            </Button>
          </HStack>
          <TableContainer
            borderWidth="1px"
            borderColor="gray.200"
            borderRadius="md"
            bg="white"
          >
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th width="40px">Select</Th>
                  <Th>Filename</Th>
                  <Th>Source path</Th>
                  <Th isNumeric>Size</Th>
                  <Th>Status</Th>
                </Tr>
              </Thead>
              <Tbody>
                {plan.files.map((file) => (
                  <Tr key={file.source_relative_path}>
                    <Td>
                      <Checkbox
                        aria-label={`Select ${file.filename}`}
                        isChecked={selectedPaths.has(file.source_relative_path)}
                        isDisabled={
                          file.status === "conflict" ||
                          busy !== null ||
                          isJobActive
                        }
                        onChange={(event) =>
                          updateSelection(
                            file.source_relative_path,
                            event.target.checked,
                          )
                        }
                      />
                    </Td>
                    <Td fontWeight="medium">{file.filename}</Td>
                    <Td>
                      <Text
                        fontSize="xs"
                        color="gray.600"
                        overflowWrap="anywhere"
                      >
                        {file.source_relative_path}
                      </Text>
                    </Td>
                    <Td isNumeric whiteSpace="nowrap">
                      {formatSize(file.size_bytes)}
                    </Td>
                    <Td>
                      <Badge
                        colorScheme={
                          file.status === "new"
                            ? "green"
                            : file.status === "conflict"
                              ? "orange"
                              : "gray"
                        }
                      >
                        {statusLabels[file.status]}
                      </Badge>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </TableContainer>
          {!plan.files.length && (
            <Text color="gray.600">
              No supported GoPro videos found in this folder.
            </Text>
          )}
        </>
      )}
    </VStack>
  );
}
