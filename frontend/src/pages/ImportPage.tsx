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
import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import {
  getDetectedImportSources,
  importGoProFiles,
  scanGoProImport,
  type DetectedImportSource,
  type ImportPlan,
  type ImportResult,
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

export function ImportPage() {
  const { projectId } = useParams();
  const activeProjectId = projectId ?? "";
  const [sourcePath, setSourcePath] = useState("");
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState<"scan" | "import" | null>(null);
  const [error, setError] = useState("");
  const [detectedSources, setDetectedSources] = useState<
    DetectedImportSource[]
  >([]);
  const [detecting, setDetecting] = useState(true);
  const [detectionError, setDetectionError] = useState("");

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
    setResult(null);
    try {
      const nextPlan = await scanGoProImport(activeProjectId, path.trim());
      setPlan(nextPlan);
      setSourcePath(nextPlan.source);
      setSelectedPaths(
        new Set(
          nextPlan.files
            .filter((file) => file.status === "new")
            .map((file) => file.source_relative_path),
        ),
      );
    } catch (reason) {
      setPlan(null);
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not scan this GoPro folder.",
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
      const importResult = await importGoProFiles(
        activeProjectId,
        plan.source,
        [...selectedPaths],
      );
      setResult(importResult);
      const refreshedPlan = await scanGoProImport(activeProjectId, plan.source);
      setPlan(refreshedPlan);
      setSelectedPaths(
        new Set(
          refreshedPlan.files
            .filter((file) => file.status === "new")
            .map((file) => file.source_relative_path),
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not import selected videos.",
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

  return (
    <VStack align="stretch" spacing={5}>
      <Box>
        <Heading size="lg">Import</Heading>
        <Text color="gray.600">
          Scan a GoPro folder and copy new videos into this project.
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
              isDisabled={busy !== null}
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
              Imported {result.imported}; skipped {result.skipped};
              conflicts/errors {result.conflicts}.
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
            <FormLabel>GoPro source folder</FormLabel>
            <Input
              value={sourcePath}
              onChange={(event) => {
                setSourcePath(event.target.value);
                setPlan(null);
                setResult(null);
                setSelectedPaths(new Set());
              }}
              placeholder="C:\\ or /media/card/DCIM"
            />
          </FormControl>
          <Button
            type="submit"
            colorScheme="blue"
            isLoading={busy === "scan"}
            isDisabled={!sourcePath.trim() || busy !== null}
          >
            Scan folder
          </Button>
        </HStack>
      </Box>

      {busy === "scan" && (
        <HStack role="status">
          <Spinner size="sm" />
          <Text>Scanning GoPro videos…</Text>
        </HStack>
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
                isDisabled={!plan.new_files || busy !== null}
              >
                Select all new
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectedPaths(new Set())}
                isDisabled={!selectedPaths.size || busy !== null}
              >
                Select none
              </Button>
            </HStack>
            <Button
              colorScheme="blue"
              onClick={() => void handleImport()}
              isLoading={busy === "import"}
              isDisabled={!selectedPaths.size || busy !== null}
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
                        isDisabled={file.status !== "new" || busy !== null}
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
