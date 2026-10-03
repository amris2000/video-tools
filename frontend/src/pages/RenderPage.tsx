import {
  Alert,
  AlertIcon,
  Box,
  Button,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  Link as ChakraLink,
  Select,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getEdits,
  getExportUrl,
  getMediaJob,
  startRender,
  type EditSummary,
  type MediaJob,
} from "../api/workflows";

export function RenderPage() {
  const { projectId } = useParams();
  const activeProjectId = projectId ?? "";
  const [edits, setEdits] = useState<EditSummary[]>([]);
  const [editFilename, setEditFilename] = useState("");
  const [mode, setMode] = useState<"accurate" | "fast">("accurate");
  const [job, setJob] = useState<MediaJob | null>(null);
  const [jobStartedAt, setJobStartedAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const jobId = job?.job_id;
  const jobStatus = job?.status;

  function formatElapsed(value: number) {
    const seconds = value % 60;
    const totalMinutes = Math.floor(value / 60);
    const minutes = totalMinutes % 60;
    const hours = Math.floor(totalMinutes / 60);
    return hours
      ? `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
      : `${String(totalMinutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getEdits(activeProjectId, controller.signal)
      .then((value) => {
        if (!active) return;
        setEdits(value);
        setEditFilename((current) => current || value[0]?.filename || "");
      })
      .catch((reason) => {
        if (active && !controller.signal.aborted)
          setError(
            reason instanceof Error ? reason.message : "Could not load edits.",
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
        if (active) setJob(updated);
      } catch (reason) {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not check render status.",
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

  useEffect(() => {
    if (
      jobStartedAt === null ||
      !jobStatus ||
      !["queued", "running"].includes(jobStatus)
    )
      return;
    const updateElapsed = () => {
      setElapsedSeconds(Math.floor((Date.now() - jobStartedAt) / 1000));
    };
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [jobStartedAt, jobStatus]);

  async function submitRender() {
    if (!editFilename || (job && ["queued", "running"].includes(job.status)))
      return;
    setError("");
    const startedAt = Date.now();
    setJobStartedAt(startedAt);
    setElapsedSeconds(0);
    try {
      setJob(await startRender(activeProjectId, editFilename, mode));
    } catch (reason) {
      setJobStartedAt(null);
      setError(
        reason instanceof Error ? reason.message : "Could not start render.",
      );
    }
  }

  if (loading)
    return (
      <HStack role="status">
        <Spinner />
        <Text>Loading render options…</Text>
      </HStack>
    );
  const running = Boolean(job && ["queued", "running"].includes(job.status));
  const completed = job?.status === "completed" && job.output_filename;

  return (
    <VStack align="stretch" spacing={6}>
      <Box>
        <Heading size="lg">Render</Heading>
        <Text color="gray.600">
          Render an edit to the project exports directory.
        </Text>
      </Box>
      {error && (
        <Alert status="error">
          <AlertIcon />
          {error}
        </Alert>
      )}
      {!edits.length ? (
        <Alert status="info">
          <AlertIcon />
          <Text>
            No edits are available.{" "}
            <ChakraLink
              as={Link}
              to={`/projects/${activeProjectId}/editor`}
              color="blue.600"
            >
              Open Editor
            </ChakraLink>{" "}
            to create one.
          </Text>
        </Alert>
      ) : (
        <>
          <FormControl maxW="520px">
            <FormLabel>Edit</FormLabel>
            <Select
              value={editFilename}
              onChange={(event) => setEditFilename(event.target.value)}
              isDisabled={running}
            >
              {edits.map((edit) => (
                <option key={edit.filename} value={edit.filename}>
                  {edit.filename} ({edit.clip_count ?? "?"} clips)
                </option>
              ))}
            </Select>
          </FormControl>
          <FormControl maxW="360px">
            <FormLabel>Render mode</FormLabel>
            <Select
              value={mode}
              onChange={(event) =>
                setMode(event.target.value as "accurate" | "fast")
              }
              isDisabled={running}
            >
              <option value="accurate">Accurate: exact cuts, re-encoded</option>
              <option value="fast">
                Fast: stream copy, keyframe-limited cuts
              </option>
            </Select>
          </FormControl>
          <Button
            colorScheme="blue"
            width="fit-content"
            onClick={() => void submitRender()}
            isDisabled={!editFilename || running}
            isLoading={running}
          >
            Start render
          </Button>
        </>
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
                ? "Render queued"
                : job.status === "running"
                  ? "Rendering…"
                  : job.status === "completed"
                    ? "Render complete"
                    : "Render failed"}
            </Text>
            {job.status === "failed" && <Text>{job.error}</Text>}
            {completed && <Text>{job.output_filename}</Text>}
            {running && (
              <Text fontSize="sm">
                Elapsed: {formatElapsed(elapsedSeconds)} · This operation
                continues in the local application process.
              </Text>
            )}
          </VStack>
        </Alert>
      )}

      {completed && (
        <Box
          bg="black"
          borderRadius="md"
          overflow="hidden"
          maxW="1000px"
          display="flex"
          justifyContent="center"
        >
          <video
            controls
            preload="metadata"
            style={{
              display: "block",
              width: "auto",
              height: "auto",
              maxWidth: "100%",
              maxHeight: 560,
            }}
            src={getExportUrl(activeProjectId, completed)}
          />
        </Box>
      )}
    </VStack>
  );
}
