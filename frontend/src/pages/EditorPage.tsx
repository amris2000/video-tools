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
  Input,
  Select,
  SimpleGrid,
  Spinner,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useRef, useState } from "react";
import {
  FiArrowDown,
  FiArrowUp,
  FiEdit2,
  FiPlay,
  FiPlus,
  FiSave,
  FiTrash2,
} from "react-icons/fi";
import { useParams } from "react-router-dom";
import { ClipBrowser } from "../components/clips/ClipBrowser";
import { getClips, type Clip } from "../api/clips";
import { getProject, type Project } from "../api/projects";
import {
  createEdit,
  deleteEdit,
  getEdit,
  getEdits,
  getMediaUrl,
  renameEdit,
  saveEdit,
  type EditDocument,
  type EditSummary,
} from "../api/workflows";

type TimelineOccurrence = {
  id: string;
  file: string;
  start: number;
  end: number;
  label?: string;
};

function serializeEdit(
  output: string,
  occurrences: TimelineOccurrence[],
): EditDocument {
  return {
    version: 1,
    output,
    clips: occurrences.map(({ file, start, end, label }) => ({
      file,
      start,
      end,
      ...(label?.trim() ? { label: label.trim() } : {}),
    })),
  };
}

function makeOccurrences(document: EditDocument): TimelineOccurrence[] {
  return document.clips.map((clip) => ({ ...clip, id: crypto.randomUUID() }));
}

function clipsPathPrefix(value: string | undefined) {
  return (value ?? "clips")
    .replace(/\\/g, "/")
    .replace(/^\.\//, "")
    .replace(/\/$/, "");
}

function projectClipPath(file: string, prefix: string) {
  return prefix ? `${prefix}/${file}` : file;
}

function editClipPath(path: string, prefix: string) {
  return prefix && path.startsWith(`${prefix}/`)
    ? path.slice(prefix.length + 1)
    : path;
}

function seconds(value: number) {
  return `${value.toFixed(3)} s`;
}

export function EditorPage() {
  const { projectId } = useParams();
  const activeProjectId = projectId ?? "";
  const [project, setProject] = useState<Project | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [edits, setEdits] = useState<EditSummary[]>([]);
  const [filename, setFilename] = useState("");
  const [output, setOutput] = useState("");
  const [occurrences, setOccurrences] = useState<TimelineOccurrence[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedClipPaths, setSelectedClipPaths] = useState<string[]>([]);
  const [loadedProjectId, setLoadedProjectId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedSnapshot, setSavedSnapshot] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);

  const selectedOccurrence =
    occurrences.find((item) => item.id === selectedId) ?? null;
  const selectedFile = selectedOccurrence?.file ?? null;
  const selectedStart = selectedOccurrence?.start ?? 0;
  const loading = loadedProjectId !== activeProjectId;
  const documentValue = serializeEdit(output, occurrences);
  const snapshot = JSON.stringify(documentValue);
  const dirty = Boolean(filename) && snapshot !== savedSnapshot;
  const clipByPath = new Map(clips.map((clip) => [clip.path, clip]));
  const clipsPrefix = clipsPathPrefix(project?.paths.clips);
  const sourceDuration = selectedOccurrence
    ? (clipByPath.get(projectClipPath(selectedOccurrence.file, clipsPrefix))
        ?.duration ?? null)
    : null;

  useEffect(() => {
    if (!activeProjectId) return;
    const controller = new AbortController();
    let active = true;
    Promise.all([
      getProject(activeProjectId),
      getClips(activeProjectId, controller.signal),
      getEdits(activeProjectId, controller.signal),
    ])
      .then(async ([projectInfo, clipList, editList]) => {
        if (!active) return;
        setError("");
        setProject(projectInfo);
        setClips(clipList);
        setEdits(editList);
        if (editList.length) {
          const document = await getEdit(activeProjectId, editList[0].filename);
          if (!active) return;
          const nextOccurrences = makeOccurrences(document);
          setFilename(editList[0].filename);
          setOutput(document.output);
          setOccurrences(nextOccurrences);
          setSelectedId(nextOccurrences[0]?.id ?? null);
          setSavedSnapshot(JSON.stringify(document));
        } else {
          setFilename("");
          setOutput("");
          setOccurrences([]);
          setSelectedId(null);
          setSavedSnapshot("");
        }
      })
      .catch((reason) => {
        if (active && !controller.signal.aborted) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load editor data.",
          );
        }
      })
      .finally(() => {
        if (active) setLoadedProjectId(activeProjectId);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [activeProjectId]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !selectedId || !selectedFile) {
      video?.pause();
      video?.removeAttribute("src");
      video?.load();
      return;
    }

    const seekToOccurrence = () => {
      if (video.dataset.currentOccurrence === selectedId) {
        video.currentTime = selectedStart;
      }
    };
    video.dataset.currentOccurrence = selectedId;

    if (video.dataset.currentSource !== selectedFile) {
      video.dataset.currentSource = selectedFile;
      video.src = getMediaUrl(activeProjectId, selectedFile);
      video.addEventListener("loadedmetadata", seekToOccurrence, {
        once: true,
      });
      video.load();
      return () =>
        video.removeEventListener("loadedmetadata", seekToOccurrence);
    }

    if (video.readyState >= 1) {
      seekToOccurrence();
    } else {
      video.addEventListener("loadedmetadata", seekToOccurrence, {
        once: true,
      });
      return () =>
        video.removeEventListener("loadedmetadata", seekToOccurrence);
    }
  }, [activeProjectId, selectedId, selectedFile, selectedStart]);

  async function reloadEdits(selectedFilename?: string) {
    const editList = await getEdits(activeProjectId);
    setEdits(editList);
    const nextFilename = selectedFilename ?? filename;
    if (!nextFilename) return;
    const document = await getEdit(activeProjectId, nextFilename);
    const nextOccurrences = makeOccurrences(document);
    setFilename(nextFilename);
    setOutput(document.output);
    setOccurrences(nextOccurrences);
    setSelectedId(nextOccurrences[0]?.id ?? null);
    setSavedSnapshot(JSON.stringify(document));
  }

  async function openEdit(nextFilename: string) {
    if (!nextFilename || nextFilename === filename) return;
    if (dirty && !window.confirm("Discard unsaved timeline changes?")) return;
    setBusy(true);
    setError("");
    try {
      await reloadEdits(nextFilename);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not open edit.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate() {
    if (
      dirty &&
      !window.confirm("Discard unsaved timeline changes and create a new edit?")
    )
      return;
    setBusy(true);
    setError("");
    try {
      const created = await createEdit(activeProjectId);
      await reloadEdits(created.filename);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not create edit.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    if (!filename) return;
    setBusy(true);
    setError("");
    try {
      const saved = await saveEdit(activeProjectId, filename, documentValue);
      setOutput(saved.document.output);
      setSavedSnapshot(JSON.stringify(saved.document));
      await getEdits(activeProjectId).then(setEdits);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not save edit.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRename() {
    if (!filename || dirty) return;
    const nextFilename = window.prompt("New edit filename", filename);
    if (!nextFilename || nextFilename === filename) return;
    setBusy(true);
    setError("");
    try {
      const renamed = await renameEdit(activeProjectId, filename, nextFilename);
      await getEdits(activeProjectId).then(setEdits);
      setFilename(renamed.filename);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not rename edit.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (
      !filename ||
      !window.confirm(
        `Delete ${filename}? This does not delete rendered videos.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await deleteEdit(activeProjectId, filename);
      const editList = await getEdits(activeProjectId);
      setEdits(editList);
      if (editList.length) await reloadEdits(editList[0].filename);
      else {
        setFilename("");
        setOutput("");
        setOccurrences([]);
        setSelectedId(null);
        setSavedSnapshot("");
      }
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not delete edit.",
      );
    } finally {
      setBusy(false);
    }
  }

  function addSelectedClips() {
    const added = selectedClipPaths.flatMap((path) => {
      const source = clipByPath.get(path);
      if (!source) return [];
      const file = editClipPath(path, clipsPrefix);
      const end = Math.max(0.001, Math.min(3, source.duration ?? 3));
      return [
        {
          id: crypto.randomUUID(),
          file,
          start: 0,
          end,
          label: `Sample from ${source.name}`,
        },
      ];
    });
    if (!added.length) return;
    setOccurrences((current) => [...current, ...added]);
    setSelectedId(added[added.length - 1].id);
    setSelectedClipPaths([]);
  }

  function updateOccurrence(id: string, changes: Partial<TimelineOccurrence>) {
    setOccurrences((current) =>
      current.map((item) => (item.id === id ? { ...item, ...changes } : item)),
    );
  }

  function moveOccurrence(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= occurrences.length) return;
    setOccurrences((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function removeOccurrence(id: string, index: number) {
    const next = occurrences.filter((item) => item.id !== id);
    setOccurrences(next);
    if (selectedId === id)
      setSelectedId(next[Math.min(index, next.length - 1)]?.id ?? null);
  }

  function updateTime(field: "start" | "end", value: string) {
    if (!selectedOccurrence) return;
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) return;
    const nextStart = field === "start" ? number : selectedOccurrence.start;
    const nextEnd = field === "end" ? number : selectedOccurrence.end;
    if (
      nextEnd <= nextStart ||
      (sourceDuration !== null && nextEnd > sourceDuration)
    )
      return;
    updateOccurrence(selectedOccurrence.id, { [field]: number });
  }

  function playSelection() {
    const video = videoRef.current;
    if (!video || !selectedOccurrence) return;
    video.currentTime = selectedOccurrence.start;
    void video.play();
  }

  if (!activeProjectId) return null;
  if (loading)
    return (
      <HStack role="status">
        <Spinner />
        <Text>Loading editor…</Text>
      </HStack>
    );

  return (
    <VStack align="stretch" spacing={6}>
      <HStack justify="space-between" align="start" flexWrap="wrap">
        <Box>
          <Heading size="lg">Editor</Heading>
          <Text color="gray.600">Build an ordered edit from source clips.</Text>
        </Box>
        <Text color={dirty ? "orange.700" : "green.700"} role="status">
          {dirty ? "Unsaved changes" : "Saved"}
        </Text>
      </HStack>

      {error && (
        <Alert status="error">
          <AlertIcon />
          {error}
        </Alert>
      )}

      <HStack align="end" spacing={3} flexWrap="wrap">
        <FormControl maxW="360px">
          <FormLabel>Edit</FormLabel>
          <Select
            value={filename}
            onChange={(event) => void openEdit(event.target.value)}
            isDisabled={busy}
            placeholder="Select an edit"
          >
            {edits.map((edit) => (
              <option key={edit.filename} value={edit.filename}>
                {edit.filename} ({edit.clip_count ?? "?"})
              </option>
            ))}
          </Select>
        </FormControl>
        <Button
          leftIcon={<FiPlus />}
          onClick={() => void handleCreate()}
          isDisabled={busy}
        >
          New
        </Button>
        <Button
          leftIcon={<FiSave />}
          colorScheme="blue"
          onClick={() => void handleSave()}
          isDisabled={!filename || !dirty || busy}
          isLoading={busy}
        >
          Save
        </Button>
        <Button
          leftIcon={<FiEdit2 />}
          onClick={() => void handleRename()}
          isDisabled={!filename || dirty || busy}
        >
          Rename
        </Button>
        <Button
          leftIcon={<FiTrash2 />}
          colorScheme="red"
          variant="outline"
          onClick={() => void handleDelete()}
          isDisabled={!filename || busy}
        >
          Delete
        </Button>
      </HStack>

      <FormControl maxW="560px">
        <FormLabel>Render output filename</FormLabel>
        <Input
          value={output}
          onChange={(event) => setOutput(event.target.value)}
          placeholder="final-video.mp4"
          isDisabled={!filename}
        />
      </FormControl>

      <Divider />

      <SimpleGrid columns={{ base: 1, xl: 2 }} spacing={6} alignItems="start">
        <VStack align="stretch" spacing={4}>
          <HStack justify="space-between">
            <Heading size="md">Timeline</Heading>
            <Text color="gray.600">{occurrences.length} occurrences</Text>
          </HStack>
          {!occurrences.length ? (
            <Text color="gray.600">
              Add source clips below to begin this edit.
            </Text>
          ) : (
            occurrences.map((item, index) => (
              <Box
                key={item.id}
                borderWidth="1px"
                borderColor={item.id === selectedId ? "blue.500" : "gray.200"}
                borderRadius="md"
                bg="white"
                p={4}
              >
                <HStack align="start" justify="space-between" spacing={3}>
                  <Button
                    variant="link"
                    color="gray.900"
                    whiteSpace="normal"
                    height="auto"
                    textAlign="left"
                    onClick={() => setSelectedId(item.id)}
                  >
                    <Stack align="start" spacing={1}>
                      <Text fontWeight="bold">
                        {index + 1}. {item.label || item.file.split("/").at(-1)}
                      </Text>
                      <Text
                        fontSize="sm"
                        color="gray.600"
                        overflowWrap="anywhere"
                      >
                        {item.file}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        {seconds(item.start)} – {seconds(item.end)}
                      </Text>
                    </Stack>
                  </Button>
                  <HStack spacing={1} flexShrink={0}>
                    <Button
                      size="sm"
                      aria-label="Move occurrence up"
                      title="Move up"
                      leftIcon={<FiArrowUp />}
                      onClick={() => moveOccurrence(index, -1)}
                      isDisabled={index === 0}
                    />
                    <Button
                      size="sm"
                      aria-label="Move occurrence down"
                      title="Move down"
                      leftIcon={<FiArrowDown />}
                      onClick={() => moveOccurrence(index, 1)}
                      isDisabled={index === occurrences.length - 1}
                    />
                    <Button
                      size="sm"
                      aria-label="Remove occurrence"
                      title="Remove occurrence"
                      colorScheme="red"
                      variant="ghost"
                      leftIcon={<FiTrash2 />}
                      onClick={() => removeOccurrence(item.id, index)}
                    />
                  </HStack>
                </HStack>
              </Box>
            ))
          )}
        </VStack>

        <VStack align="stretch" spacing={4}>
          <Heading size="md">Selected occurrence</Heading>
          {!selectedOccurrence ? (
            <Text color="gray.600">
              Select a timeline occurrence to preview and trim it.
            </Text>
          ) : (
            <>
              <Box bg="black" borderRadius="md" overflow="hidden">
                <video
                  ref={videoRef}
                  controls
                  preload="metadata"
                  style={{ width: "100%", maxHeight: 420 }}
                  onTimeUpdate={(event) => {
                    if (
                      selectedOccurrence &&
                      event.currentTarget.currentTime >= selectedOccurrence.end
                    )
                      event.currentTarget.pause();
                  }}
                />
              </Box>
              <Text color="gray.600" overflowWrap="anywhere">
                {selectedOccurrence.file}
              </Text>
              <HStack>
                <Button leftIcon={<FiPlay />} onClick={playSelection}>
                  Play selection
                </Button>
                <Text color="gray.600">
                  {seconds(selectedOccurrence.end - selectedOccurrence.start)}
                </Text>
              </HStack>
              <SimpleGrid columns={{ base: 1, sm: 2 }} spacing={3}>
                <FormControl>
                  <FormLabel>Start (seconds)</FormLabel>
                  <Input
                    type="number"
                    min={0}
                    max={sourceDuration ?? undefined}
                    step={0.001}
                    value={selectedOccurrence.start}
                    onChange={(event) =>
                      updateTime("start", event.target.value)
                    }
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>End (seconds)</FormLabel>
                  <Input
                    type="number"
                    min={0.001}
                    max={sourceDuration ?? undefined}
                    step={0.001}
                    value={selectedOccurrence.end}
                    onChange={(event) => updateTime("end", event.target.value)}
                  />
                </FormControl>
              </SimpleGrid>
              <HStack>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    updateTime(
                      "start",
                      String(
                        videoRef.current?.currentTime ??
                          selectedOccurrence.start,
                      ),
                    )
                  }
                >
                  Set start to playhead
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    updateTime(
                      "end",
                      String(
                        videoRef.current?.currentTime ?? selectedOccurrence.end,
                      ),
                    )
                  }
                >
                  Set end to playhead
                </Button>
              </HStack>
              <FormControl>
                <FormLabel>Label</FormLabel>
                <Input
                  value={selectedOccurrence.label ?? ""}
                  onChange={(event) =>
                    updateOccurrence(selectedOccurrence.id, {
                      label: event.target.value,
                    })
                  }
                  placeholder="Optional note"
                />
              </FormControl>
            </>
          )}
        </VStack>
      </SimpleGrid>

      <Divider />
      <HStack justify="space-between" align="end" flexWrap="wrap">
        <Box>
          <Heading size="md">Source clips</Heading>
          <Text color="gray.600">
            Each add creates a separate timeline occurrence.
          </Text>
        </Box>
        <Button
          leftIcon={<FiPlus />}
          colorScheme="blue"
          onClick={addSelectedClips}
          isDisabled={!selectedClipPaths.length || !filename}
        >
          Add selected to timeline ({selectedClipPaths.length})
        </Button>
      </HStack>
      {!filename && (
        <Text color="orange.700">
          Create or open an edit before adding clips.
        </Text>
      )}
      <ClipBrowser
        key={activeProjectId}
        projectId={activeProjectId}
        mode="select"
        selectedClipPaths={selectedClipPaths}
        onSelectionChange={setSelectedClipPaths}
      />
    </VStack>
  );
}
