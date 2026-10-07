import {
  Alert,
  AlertIcon,
  Button,
  HStack,
  IconButton,
  Select,
  Tooltip,
  SimpleGrid,
  Spinner,
  Text,
  VStack,
  useDisclosure,
} from "@chakra-ui/react";
import { useEffect, useMemo, useState } from "react";
import { FiBookOpen } from "react-icons/fi";
import { FiMapPin } from "react-icons/fi";
import { getClips, type Clip } from "../../api/clips";
import { getMediaUrl } from "../../api/workflows";
import { ClipJournalModal } from "./ClipJournalModal";
import { ClipMapModal } from "./ClipMapModal";
import { VideoPreviewModal } from "../media/VideoPreviewModal";
import { ClipCard } from "./ClipCard";

export type ClipBrowserProps = {
  projectId: string;
  enableDateFilterInView?: boolean;
} & (
  | { mode?: "view"; selectedClipPaths?: never; onSelectionChange?: never }
  | {
      mode: "select";
      /** Controlled selection; the consumer owns it and scopes it to projectId. */
      selectedClipPaths: readonly string[];
      onSelectionChange: (paths: string[]) => void;
    }
);

/** Shared catalog, loading states and cards for viewing and picking clips. */
export function ClipBrowser(props: ClipBrowserProps) {
  const { projectId } = props;
  const ALL_CLIPS = "__all__";
  const [result, setResult] = useState<{
    projectId: string;
    clips?: Clip[];
    error?: string;
  } | null>(null);
  const [previewClip, setPreviewClip] = useState<Clip | null>(null);
  const [journalClip, setJournalClip] = useState<Clip | null>(null);
  const [mapClip, setMapClip] = useState<Clip | null>(null);
  const [selectedDateGroup, setSelectedDateGroup] = useState<string | null>(
    null,
  );
  const [attempt, setAttempt] = useState(0);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const {
    isOpen: isJournalOpen,
    onOpen: onJournalOpen,
    onClose: onJournalClose,
  } = useDisclosure();

  function clipDateGroup(clip: Clip): string | null {
    const mediaFirst = clip.media_path.replace(/\\/g, "/").split("/")[0] ?? "";
    if (/^\d{8}$/.test(mediaFirst)) return mediaFirst;

    const timestamp = clip.creation_time ?? "";
    const match = timestamp.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) return `${match[1]}${match[2]}${match[3]}`;

    return null;
  }

  const clips = result?.clips ?? [];

  const dateGroups = useMemo(() => {
    const values = [
      ...new Set(clips.map(clipDateGroup).filter(Boolean)),
    ] as string[];
    return values.sort((a, b) => b.localeCompare(a));
  }, [clips]);

  const dateGroupCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const clip of clips) {
      const group = clipDateGroup(clip);
      if (!group) continue;
      counts.set(group, (counts.get(group) ?? 0) + 1);
    }
    return counts;
  }, [clips]);
  const {
    isOpen: isMapOpen,
    onOpen: onMapOpen,
    onClose: onMapClose,
  } = useDisclosure();
  const isViewMode = props.mode !== "select";
  const showDateFilter =
    props.mode === "select" || (isViewMode && props.enableDateFilterInView);

  useEffect(() => {
    const controller = new AbortController();
    getClips(projectId, controller.signal)
      .then((clips) => {
        if (!controller.signal.aborted) setResult({ projectId, clips });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setResult({
            projectId,
            error:
              error instanceof Error ? error.message : "Could not load clips.",
          });
      });
    return () => controller.abort();
  }, [projectId, attempt]);

  useEffect(() => {
    if (!showDateFilter) {
      setSelectedDateGroup(null);
      return;
    }

    if (selectedDateGroup === null) {
      setSelectedDateGroup(ALL_CLIPS);
      return;
    }

    if (
      selectedDateGroup !== ALL_CLIPS &&
      !dateGroups.includes(selectedDateGroup)
    ) {
      setSelectedDateGroup(ALL_CLIPS);
    }
  }, [showDateFilter, dateGroups, selectedDateGroup]);

  const visibleClips =
    showDateFilter && selectedDateGroup && selectedDateGroup !== ALL_CLIPS
      ? clips.filter((clip) => clipDateGroup(clip) === selectedDateGroup)
      : clips;

  const selected = new Set(
    props.mode === "select" ? props.selectedClipPaths : [],
  );
  const totalSelected =
    props.mode === "select" ? props.selectedClipPaths.length : 0;
  const visibleSelected = visibleClips.filter((clip) =>
    selected.has(clip.path),
  ).length;

  if (!result || result.projectId !== projectId) {
    return (
      <HStack role="status">
        <Spinner />
        <Text>Loading clips…</Text>
      </HStack>
    );
  }
  if (result.error) {
    return (
      <Alert status="error">
        <AlertIcon />
        {result.error}
        <Button
          ml={4}
          onClick={() => {
            setResult(null);
            setAttempt((value) => value + 1);
          }}
        >
          Retry
        </Button>
      </Alert>
    );
  }
  if (!clips.length) return <Text>No clips in this project yet.</Text>;

  function openPreview(clip: Clip) {
    setPreviewClip(clip);
    onOpen();
  }

  function closePreview() {
    setPreviewClip(null);
    onClose();
  }

  function openJournal(clip: Clip) {
    setJournalClip(clip);
    onJournalOpen();
  }

  function closeJournal() {
    setJournalClip(null);
    onJournalClose();
  }

  function openMap(clip: Clip) {
    setMapClip(clip);
    onMapOpen();
  }

  function closeMap() {
    setMapClip(null);
    onMapClose();
  }

  function toggle(path: string) {
    if (props.mode !== "select") return;
    const next = new Set(props.selectedClipPaths);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    props.onSelectionChange([...next]);
  }

  return (
    <VStack align="stretch" spacing={isViewMode ? 2 : 4}>
      <HStack justify="space-between">
        <Text color="gray.600">{visibleClips.length} clips</Text>
        {showDateFilter && (
          <HStack>
            <Select
              size="sm"
              width="220px"
              value={selectedDateGroup ?? ALL_CLIPS}
              onChange={(event) => setSelectedDateGroup(event.target.value)}
            >
              <option value={ALL_CLIPS}>All clips ({clips.length})</option>
              {dateGroups.map((group) => (
                <option key={group} value={group}>
                  {group} ({dateGroupCounts.get(group) ?? 0})
                </option>
              ))}
            </Select>
            {props.mode === "select" && (
              <>
                <Text role="status">
                  {totalSelected} selected
                  {selectedDateGroup !== ALL_CLIPS
                    ? ` (${visibleSelected} in view)`
                    : ""}
                </Text>
                <Button
                  size="sm"
                  isDisabled={
                    !visibleClips.length ||
                    visibleSelected === visibleClips.length
                  }
                  onClick={() => {
                    if (props.mode !== "select") return;
                    const next = new Set(props.selectedClipPaths);
                    for (const clip of visibleClips) next.add(clip.path);
                    props.onSelectionChange([...next]);
                  }}
                >
                  Select all
                </Button>
                <Button
                  size="sm"
                  isDisabled={!visibleSelected}
                  onClick={() => {
                    if (props.mode !== "select") return;
                    const remove = new Set(
                      visibleClips.map((clip) => clip.path),
                    );
                    props.onSelectionChange(
                      props.selectedClipPaths.filter(
                        (path) => !remove.has(path),
                      ),
                    );
                  }}
                >
                  Deselect all
                </Button>
                <Button
                  size="sm"
                  isDisabled={!totalSelected}
                  onClick={() => props.onSelectionChange([])}
                >
                  Clear selection
                </Button>
              </>
            )}
          </HStack>
        )}
      </HStack>
      <SimpleGrid
        columns={
          isViewMode
            ? { base: 2, sm: 3, md: 4, lg: 5, xl: 6 }
            : { base: 1, md: 2, xl: 3, "2xl": 4 }
        }
        spacing={isViewMode ? 2 : 4}
      >
        {visibleClips.map((clip) =>
          isViewMode ? (
            <VStack key={clip.path} align="stretch" spacing={2}>
              <ClipCard
                clip={clip}
                compact
                selected={selected.has(clip.path)}
                onPreview={() => openPreview(clip)}
              />

              <HStack justify="flex-end">
                <Tooltip
                  label={
                    clip.journal ? "Open related journal" : "No journal link"
                  }
                >
                  <IconButton
                    aria-label="Open related journal"
                    size="sm"
                    icon={<FiBookOpen />}
                    variant="outline"
                    colorScheme={clip.journal ? "blue" : undefined}
                    isDisabled={!clip.journal}
                    onClick={() => openJournal(clip)}
                  />
                </Tooltip>

                <Tooltip
                  label={
                    clip.gps?.available &&
                    typeof clip.gps.latitude === "number" &&
                    typeof clip.gps.longitude === "number"
                      ? "Open clip location"
                      : "No GPS location"
                  }
                >
                  <IconButton
                    aria-label="Open clip location"
                    size="sm"
                    icon={<FiMapPin />}
                    variant="outline"
                    colorScheme={
                      clip.gps?.available &&
                      typeof clip.gps.latitude === "number" &&
                      typeof clip.gps.longitude === "number"
                        ? "green"
                        : undefined
                    }
                    isDisabled={
                      !clip.gps?.available ||
                      typeof clip.gps.latitude !== "number" ||
                      typeof clip.gps.longitude !== "number"
                    }
                    onClick={() => openMap(clip)}
                  />
                </Tooltip>
              </HStack>
            </VStack>
          ) : (
            <ClipCard
              key={clip.path}
              clip={clip}
              compact={false}
              selected={selected.has(clip.path)}
              onPreview={() => openPreview(clip)}
              onToggle={
                props.mode === "select" ? () => toggle(clip.path) : undefined
              }
            />
          ),
        )}
      </SimpleGrid>
      <VideoPreviewModal
        isOpen={isOpen}
        onClose={closePreview}
        title={previewClip?.name ?? "Clip preview"}
        videoUrl={
          previewClip ? getMediaUrl(projectId, previewClip.media_path) : ""
        }
        metadata={
          previewClip && (
            <>
              <Text fontWeight="semibold">
                {previewClip.duration === null
                  ? "Duration unavailable"
                  : `${Math.floor(previewClip.duration / 60)}:${String(Math.floor(previewClip.duration % 60)).padStart(2, "0")}`}
              </Text>
              {previewClip.width && previewClip.height && (
                <Text color="gray.600">
                  {previewClip.width} × {previewClip.height}
                </Text>
              )}
              {previewClip.fps && (
                <Text color="gray.600">{previewClip.fps} fps</Text>
              )}
              {previewClip.creation_time && (
                <Text color="gray.600">
                  {previewClip.creation_time.replace("T", " ")}
                </Text>
              )}
              <Text fontSize="sm" color="gray.500" overflowWrap="anywhere">
                {previewClip.path}
              </Text>
            </>
          )
        }
      />
      <ClipJournalModal
        isOpen={isJournalOpen}
        onClose={closeJournal}
        clip={journalClip}
      />
      <ClipMapModal isOpen={isMapOpen} onClose={closeMap} clip={mapClip} />
    </VStack>
  );
}
