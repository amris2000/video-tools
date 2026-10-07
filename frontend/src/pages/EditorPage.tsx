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
  IconButton,
  Image,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  RangeSlider,
  RangeSliderFilledTrack,
  RangeSliderThumb,
  RangeSliderTrack,
  Select,
  SimpleGrid,
  Spinner,
  Text,
  Tooltip,
  VStack,
  useDisclosure,
} from "@chakra-ui/react";
import { useEffect, useRef, useState } from "react";
import {
  FiArrowDown,
  FiArrowUp,
  FiChevronsDown,
  FiChevronsUp,
  FiCopy,
  FiEdit2,
  FiPlay,
  FiPlus,
  FiSave,
  FiSkipBack,
  FiSkipForward,
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
  speed: number;
};

const SPEED_OPTIONS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 3, 4];

function serializeEdit(
  output: string,
  occurrences: TimelineOccurrence[],
): EditDocument {
  return {
    version: 1,
    output,
    // speed is omitted when 1 so documents without speed changes stay
    // readable by older tooling that only knows version-1 fields.
    clips: occurrences.map(({ file, start, end, label, speed }) => ({
      file,
      start,
      end,
      ...(label?.trim() ? { label: label.trim() } : {}),
      ...(speed !== 1 ? { speed } : {}),
    })),
  };
}

function makeOccurrences(document: EditDocument): TimelineOccurrence[] {
  return document.clips.map((clip) => ({
    ...clip,
    id: crypto.randomUUID(),
    speed: clip.speed ?? 1,
  }));
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

function formatDuration(value: number) {
  const minutes = Math.floor(value / 60);
  const remainder = value - minutes * 60;
  return minutes > 0
    ? `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`
    : `${remainder.toFixed(1)} s`;
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
  const stopAtEndRef = useRef(false);
  const lastSeekOccurrenceRef = useRef<string | null>(null);
  const {
    isOpen: isClipPickerOpen,
    onOpen: openClipPicker,
    onClose: closeClipPicker,
  } = useDisclosure();
  const {
    isOpen: isQuickPreviewOpen,
    onOpen: openQuickPreview,
    onClose: closeQuickPreview,
  } = useDisclosure();
  const quickPreviewVideoRef = useRef<HTMLVideoElement>(null);
  const [quickPreviewIndex, setQuickPreviewIndex] = useState(0);
  const [quickPreviewError, setQuickPreviewError] = useState("");
  const [timeDraft, setTimeDraft] = useState<{ start: string; end: string }>({
    start: "",
    end: "",
  });
  const [timeError, setTimeError] = useState("");

  const selectedOccurrence =
    occurrences.find((item) => item.id === selectedId) ?? null;
  const selectedFile = selectedOccurrence?.file ?? null;
  const selectedStart = selectedOccurrence?.start ?? 0;
  const selectedSpeed = selectedOccurrence?.speed ?? 1;
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
  const quickPreviewOccurrence = occurrences[quickPreviewIndex] ?? null;
  const totalTimelineSeconds = occurrences.reduce(
    (total, item) => total + Math.max(0, item.end - item.start) / item.speed,
    0,
  );
  const quickPreviewVideoUrl =
    isQuickPreviewOpen && quickPreviewOccurrence
      ? getMediaUrl(activeProjectId, quickPreviewOccurrence.file)
      : undefined;

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
      if (video) video.playbackRate = 1;
      video?.pause();
      video?.removeAttribute("src");
      video?.load();
      return;
    }

    video.playbackRate = selectedSpeed;

    const seekToOccurrence = () => {
      if (video.dataset.currentOccurrence !== selectedId) return;
      // Don't yank the playhead mid-playback when only the trim start moved.
      if (!video.paused && lastSeekOccurrenceRef.current === selectedId) return;
      video.currentTime = selectedStart;
      lastSeekOccurrenceRef.current = selectedId;
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
  }, [activeProjectId, selectedId, selectedFile, selectedStart, selectedSpeed]);

  useEffect(() => {
    stopAtEndRef.current = false;
  }, [selectedId]);

  useEffect(() => {
    if (!selectedOccurrence) {
      setTimeDraft({ start: "", end: "" });
    } else {
      setTimeDraft({
        start: String(selectedOccurrence.start),
        end: String(selectedOccurrence.end),
      });
    }
    setTimeError("");
  }, [
    selectedOccurrence?.id,
    selectedOccurrence?.start,
    selectedOccurrence?.end,
  ]);

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

  async function handleSaveAs() {
    if (!filename) return;
    const suggested = filename.endsWith(".json")
      ? filename.replace(/\.json$/i, "-copy.json")
      : `${filename}-copy`;
    const nextFilename = window.prompt("Save edit as", suggested)?.trim();
    if (!nextFilename || nextFilename === filename) return;

    setBusy(true);
    setError("");
    let created = false;

    try {
      await createEdit(activeProjectId, nextFilename);
      created = true;
      await saveEdit(activeProjectId, nextFilename, documentValue);
      await reloadEdits(nextFilename);
    } catch (reason) {
      if (created) {
        try {
          await deleteEdit(activeProjectId, nextFilename);
        } catch {
          // Keep the original error as primary if cleanup fails.
        }
      }
      setError(
        reason instanceof Error ? reason.message : "Could not save edit as.",
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
          speed: 1,
        },
      ];
    });
    if (!added.length) return;
    setOccurrences((current) => [...current, ...added]);
    setSelectedId(added[added.length - 1].id);
    setSelectedClipPaths([]);
    closeClipPicker();
  }

  function updateOccurrence(id: string, changes: Partial<TimelineOccurrence>) {
    setOccurrences((current) =>
      current.map((item) => (item.id === id ? { ...item, ...changes } : item)),
    );
  }

  function moveOccurrence(
    id: string,
    destination: "start" | "earlier" | "later" | "end",
  ) {
    setOccurrences((current) => {
      const index = current.findIndex((item) => item.id === id);
      if (index < 0) return current;
      const next = [...current];
      const [occurrence] = next.splice(index, 1);
      const target =
        destination === "start"
          ? 0
          : destination === "end"
            ? next.length
            : destination === "earlier"
              ? Math.max(0, index - 1)
              : Math.min(next.length, index + 1);
      next.splice(target, 0, occurrence);
      return next;
    });
    setSelectedId(id);
  }

  function duplicateOccurrence(id: string) {
    const duplicateId = crypto.randomUUID();
    setOccurrences((current) => {
      const index = current.findIndex((item) => item.id === id);
      if (index < 0) return current;
      const duplicate = { ...current[index], id: duplicateId };
      const next = [...current];
      next.splice(index + 1, 0, duplicate);
      return next;
    });
    setSelectedId(duplicateId);
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

  function commitTimeDraft() {
    if (!selectedOccurrence) return;
    const start = Number(timeDraft.start);
    const end = Number(timeDraft.end);

    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      setTimeError("Start and end must be numbers.");
      return;
    }
    if (start < 0) {
      setTimeError("Start must be zero or greater.");
      return;
    }
    if (end <= start) {
      setTimeError("End must be greater than start.");
      return;
    }
    if (sourceDuration !== null && end > sourceDuration) {
      setTimeError(
        `End cannot exceed the source duration (${seconds(sourceDuration)}).`,
      );
      return;
    }

    setTimeError("");
    updateOccurrence(selectedOccurrence.id, { start, end });
  }

  const timeDraftDirty =
    selectedOccurrence !== null &&
    (timeDraft.start !== String(selectedOccurrence.start) ||
      timeDraft.end !== String(selectedOccurrence.end));

  function playSelection() {
    const video = videoRef.current;
    if (!video || !selectedOccurrence) return;
    stopAtEndRef.current = true;
    video.currentTime = selectedOccurrence.start;
    void video.play();
  }

  function handleOpenQuickPreview() {
    if (!occurrences.length) return;
    setQuickPreviewIndex(0);
    setQuickPreviewError("");
    openQuickPreview();
  }

  function handleCloseQuickPreview() {
    const video = quickPreviewVideoRef.current;
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
    setQuickPreviewError("");
    closeQuickPreview();
  }

  function goToNextQuickPreviewClip() {
    setQuickPreviewIndex((current) => {
      if (current >= occurrences.length - 1) {
        quickPreviewVideoRef.current?.pause();
        return current;
      }
      return current + 1;
    });
  }

  function goToPreviousQuickPreviewClip() {
    setQuickPreviewIndex((current) => Math.max(0, current - 1));
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
          leftIcon={<FiCopy />}
          onClick={() => void handleSaveAs()}
          isDisabled={!filename || busy}
        >
          Save as
        </Button>
        <Button
          leftIcon={<FiEdit2 />}
          onClick={() => void handleRename()}
          isDisabled={!filename || dirty || busy}
        >
          Rename
        </Button>
        <Button
          leftIcon={<FiPlus />}
          onClick={openClipPicker}
          isDisabled={busy}
        >
          Add clips
        </Button>
        <Button
          leftIcon={<FiPlay />}
          onClick={handleOpenQuickPreview}
          isDisabled={!occurrences.length || busy}
        >
          Quick preview
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
      <SimpleGrid
        columns={{ base: 1, xl: 2 }}
        templateColumns={{
          base: "minmax(0, 1fr)",
          xl: "minmax(0, 0.45fr) minmax(0, 0.55fr)",
        }}
        spacing={6}
        alignItems="start"
      >
        <VStack
          align="stretch"
          spacing={5}
          order={{ base: 1, xl: 2 }}
          position={{ base: "static", xl: "sticky" }}
          top={{ xl: 4 }}
          alignSelf="start"
        >
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
                    if (!stopAtEndRef.current) return;
                    if (
                      selectedOccurrence &&
                      event.currentTarget.currentTime >= selectedOccurrence.end
                    ) {
                      stopAtEndRef.current = false;
                      event.currentTarget.pause();
                    }
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
                  {seconds(
                    (selectedOccurrence.end - selectedOccurrence.start) /
                      selectedOccurrence.speed,
                  )}
                  {selectedOccurrence.speed !== 1
                    ? ` (source ${seconds(selectedOccurrence.end - selectedOccurrence.start)})`
                    : ""}
                </Text>
              </HStack>
              {sourceDuration !== null && sourceDuration > 0 && (
                <Box px={2}>
                  <HStack justify="space-between" mb={1}>
                    <Text fontSize="xs" color="gray.500">
                      0:00
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      {seconds(sourceDuration)}
                    </Text>
                  </HStack>
                  <RangeSlider
                    min={0}
                    max={sourceDuration}
                    step={0.001}
                    value={[selectedOccurrence.start, selectedOccurrence.end]}
                    onChange={([start, end]) =>
                      updateOccurrence(selectedOccurrence.id, { start, end })
                    }
                    aria-label={["Trim start", "Trim end"]}
                    colorScheme="blue"
                  >
                    <RangeSliderTrack bg="gray.200">
                      <RangeSliderFilledTrack />
                    </RangeSliderTrack>
                    <RangeSliderThumb index={0} aria-label="Trim start" />
                    <RangeSliderThumb index={1} aria-label="Trim end" />
                  </RangeSlider>
                  <HStack justify="space-between" mt={1}>
                    <Text fontSize="xs" color="blue.700">
                      Start {seconds(selectedOccurrence.start)}
                    </Text>
                    <Text fontSize="xs" color="blue.700">
                      End {seconds(selectedOccurrence.end)}
                    </Text>
                  </HStack>
                </Box>
              )}
              <SimpleGrid columns={{ base: 1, sm: 2 }} spacing={3}>
                <FormControl isInvalid={Boolean(timeError)}>
                  <FormLabel>Start (seconds)</FormLabel>
                  <Input
                    type="number"
                    min={0}
                    max={sourceDuration ?? undefined}
                    step={0.001}
                    value={timeDraft.start}
                    onChange={(event) => {
                      setTimeError("");
                      setTimeDraft((current) => ({
                        ...current,
                        start: event.target.value,
                      }));
                    }}
                  />
                </FormControl>
                <FormControl isInvalid={Boolean(timeError)}>
                  <FormLabel>End (seconds)</FormLabel>
                  <Input
                    type="number"
                    min={0.001}
                    max={sourceDuration ?? undefined}
                    step={0.001}
                    value={timeDraft.end}
                    onChange={(event) => {
                      setTimeError("");
                      setTimeDraft((current) => ({
                        ...current,
                        end: event.target.value,
                      }));
                    }}
                  />
                </FormControl>
              </SimpleGrid>
              {timeError && (
                <Text color="red.600" fontSize="sm">
                  {timeError}
                </Text>
              )}
              <HStack>
                <Button
                  size="sm"
                  colorScheme="blue"
                  onClick={commitTimeDraft}
                  isDisabled={!timeDraftDirty}
                >
                  Update times
                </Button>
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
                <FormLabel>Speed</FormLabel>
                <Select
                  value={String(selectedOccurrence.speed)}
                  onChange={(event) =>
                    updateOccurrence(selectedOccurrence.id, {
                      speed: Number(event.target.value),
                    })
                  }
                  maxW="200px"
                >
                  {SPEED_OPTIONS.map((option) => (
                    <option key={option} value={String(option)}>
                      {option}×{option === 1 ? " (normal)" : ""}
                    </option>
                  ))}
                </Select>
                {selectedOccurrence.speed !== 1 && (
                  <Text fontSize="xs" color="gray.600" mt={1}>
                    Plays as{" "}
                    {formatDuration(
                      (selectedOccurrence.end - selectedOccurrence.start) /
                        selectedOccurrence.speed,
                    )}{" "}
                    in the rendered video. Render in accurate mode; fast mode
                    copies streams and cannot change speed.
                  </Text>
                )}
              </FormControl>
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

        <VStack align="stretch" spacing={2} order={{ base: 0, xl: 1 }}>
          <HStack justify="space-between">
            <Heading size="md">Timeline</Heading>
            <Text color="gray.600">
              {occurrences.length} occurrences ·{" "}
              {formatDuration(totalTimelineSeconds)} total
            </Text>
          </HStack>
          <Box
            minH={0}
            maxH={{ base: "none", xl: "calc(100vh - 360px)" }}
            overflowY={{ base: "visible", xl: "auto" }}
            overscrollBehavior="contain"
            pr={{ base: 0, xl: 2 }}
          >
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
                  px={3}
                  py={3}
                >
                  <HStack justify="space-between" spacing={3}>
                    <Tooltip label={item.file} placement="top" openDelay={400}>
                      <Button
                        variant="link"
                        color="gray.900"
                        whiteSpace="normal"
                        height="auto"
                        minWidth={0}
                        textAlign="left"
                        onClick={() => setSelectedId(item.id)}
                      >
                        <HStack spacing={2} align="center" minWidth={0}>
                          <Box
                            width="50px"
                            height="28px"
                            flexShrink={0}
                            borderRadius="sm"
                            overflow="hidden"
                            bg="gray.100"
                          >
                            {(() => {
                              const thumbnailUrl = clipByPath.get(
                                projectClipPath(item.file, clipsPrefix),
                              )?.thumbnail_url;
                              return thumbnailUrl ? (
                                <Image
                                  src={thumbnailUrl}
                                  alt=""
                                  loading="lazy"
                                  objectFit="cover"
                                  width="100%"
                                  height="100%"
                                />
                              ) : null;
                            })()}
                          </Box>
                          <HStack spacing={3} align="baseline" minWidth={0}>
                            <Text
                              fontSize="sm"
                              fontWeight="semibold"
                              noOfLines={1}
                            >
                              {index + 1}. {item.file.split("/").at(-1)}
                            </Text>
                            <Text
                              fontSize="xs"
                              color="gray.600"
                              whiteSpace="nowrap"
                            >
                              {seconds(item.start)} → {seconds(item.end)}
                              {item.speed !== 1 ? ` · ×${item.speed}` : ""}
                            </Text>
                          </HStack>
                        </HStack>
                      </Button>
                    </Tooltip>
                    <HStack spacing={0} flexShrink={0}>
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Duplicate occurrence"
                        title="Duplicate occurrence"
                        icon={<FiCopy />}
                        onClick={() => duplicateOccurrence(item.id)}
                      />
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Move to start"
                        title="Move to start"
                        icon={<FiChevronsUp />}
                        onClick={() => moveOccurrence(item.id, "start")}
                        isDisabled={index === 0}
                      />
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Move earlier"
                        title="Move earlier"
                        icon={<FiArrowUp />}
                        onClick={() => moveOccurrence(item.id, "earlier")}
                        isDisabled={index === 0}
                      />
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Move later"
                        title="Move later"
                        icon={<FiArrowDown />}
                        onClick={() => moveOccurrence(item.id, "later")}
                        isDisabled={index === occurrences.length - 1}
                      />
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Move to end"
                        title="Move to end"
                        icon={<FiChevronsDown />}
                        onClick={() => moveOccurrence(item.id, "end")}
                        isDisabled={index === occurrences.length - 1}
                      />
                      <IconButton
                        size="sm"
                        colorScheme="red"
                        variant="ghost"
                        aria-label="Remove occurrence"
                        title="Remove occurrence"
                        icon={<FiTrash2 />}
                        onClick={() => removeOccurrence(item.id, index)}
                      />
                    </HStack>
                  </HStack>
                </Box>
              ))
            )}
          </Box>
        </VStack>
      </SimpleGrid>

      <Modal
        isOpen={isQuickPreviewOpen}
        onClose={handleCloseQuickPreview}
        size="5xl"
        isCentered
      >
        <ModalOverlay />
        <ModalContent maxW={{ base: "calc(100vw - 24px)", xl: "1200px" }}>
          <ModalHeader>Quick preview</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={4}>
            <VStack align="stretch" spacing={3}>
              {!quickPreviewOccurrence ? (
                <Text color="gray.600">No occurrences to preview.</Text>
              ) : (
                <>
                  <Text color="gray.600">
                    Occurrence {quickPreviewIndex + 1} of {occurrences.length}
                  </Text>
                  <Box bg="black" borderRadius="md" overflow="hidden">
                    <video
                      key={quickPreviewOccurrence.id}
                      ref={quickPreviewVideoRef}
                      src={quickPreviewVideoUrl}
                      controls
                      preload="metadata"
                      style={{ width: "100%", maxHeight: 560 }}
                      onLoadStart={() => setQuickPreviewError("")}
                      onLoadedMetadata={(event) => {
                        event.currentTarget.playbackRate =
                          quickPreviewOccurrence.speed;
                        event.currentTarget.currentTime =
                          quickPreviewOccurrence.start;
                        void event.currentTarget.play().catch(() => {
                          // Browsers may still block autoplay under strict policies.
                        });
                      }}
                      onError={() =>
                        setQuickPreviewError(
                          "Could not load video for quick preview.",
                        )
                      }
                      onTimeUpdate={(event) => {
                        if (!quickPreviewOccurrence) return;
                        if (
                          event.currentTarget.currentTime >=
                          quickPreviewOccurrence.end
                        ) {
                          event.currentTarget.pause();
                          goToNextQuickPreviewClip();
                        }
                      }}
                    />
                  </Box>
                  <Text
                    color="gray.700"
                    fontWeight="semibold"
                    overflowWrap="anywhere"
                  >
                    {quickPreviewOccurrence.file}
                  </Text>
                  <Text color="gray.600">
                    {seconds(quickPreviewOccurrence.start)} to{" "}
                    {seconds(quickPreviewOccurrence.end)}
                    {quickPreviewOccurrence.speed !== 1
                      ? ` · ×${quickPreviewOccurrence.speed}`
                      : ""}
                  </Text>
                </>
              )}
              {quickPreviewError && (
                <Alert status="error">
                  <AlertIcon />
                  {quickPreviewError}
                </Alert>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter>
            <HStack>
              <Button variant="ghost" onClick={handleCloseQuickPreview}>
                Close
              </Button>
              <Button
                variant="outline"
                leftIcon={<FiSkipBack />}
                onClick={goToPreviousQuickPreviewClip}
                isDisabled={!quickPreviewOccurrence || quickPreviewIndex === 0}
              >
                Previous
              </Button>
              <Button
                onClick={() => {
                  if (!quickPreviewOccurrence) return;
                  const video = quickPreviewVideoRef.current;
                  if (!video) return;
                  video.currentTime = quickPreviewOccurrence.start;
                  void video.play();
                }}
                isDisabled={!quickPreviewOccurrence}
                leftIcon={<FiPlay />}
              >
                Replay current
              </Button>
              <Button
                variant="outline"
                rightIcon={<FiSkipForward />}
                onClick={goToNextQuickPreviewClip}
                isDisabled={
                  !quickPreviewOccurrence ||
                  quickPreviewIndex >= occurrences.length - 1
                }
              >
                Next
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal
        isOpen={isClipPickerOpen}
        onClose={closeClipPicker}
        size="6xl"
        isCentered
      >
        <ModalOverlay />
        <ModalContent maxW={{ base: "calc(100vw - 24px)", xl: "1500px" }}>
          <ModalHeader>Add clips to timeline</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack align="stretch" spacing={4}>
              <Text color="gray.600">
                Select clips with checkboxes. Click a clip card (outside
                checkbox) to preview it.
              </Text>
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
          </ModalBody>
          <ModalFooter>
            <HStack>
              <Button variant="ghost" onClick={closeClipPicker}>
                Close
              </Button>
              <Button
                leftIcon={<FiPlus />}
                colorScheme="blue"
                onClick={addSelectedClips}
                isDisabled={!selectedClipPaths.length || !filename}
              >
                Add selected to timeline ({selectedClipPaths.length})
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </VStack>
  );
}
