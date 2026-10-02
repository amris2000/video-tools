import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Heading,
  HStack,
  SimpleGrid,
  Spinner,
  Stat,
  StatLabel,
  StatNumber,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getProject, type ProjectDetails } from "../api/projects";
import {
  getMediaJob,
  startProbe,
  startThumbnails,
  type MediaJob,
} from "../api/workflows";

export function OverviewPage() {
  const { projectId } = useParams();

  const [project, setProject] = useState<ProjectDetails | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const [maintenanceJob, setMaintenanceJob] = useState<MediaJob | null>(null);
  const [maintenanceError, setMaintenanceError] = useState<string | null>(null);

  async function loadProject(activeProjectId: string) {
    setLoading(true);
    setError(null);

    try {
      const details = await getProject(activeProjectId);
      setProject(details);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load project.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!projectId) {
      setError("No project selected.");
      setLoading(false);
      return;
    }

    void loadProject(projectId);
  }, [projectId]);

  useEffect(() => {
    if (!projectId) {
      return;
    }

    const jobId = maintenanceJob?.job_id;
    const status = maintenanceJob?.status;

    if (!jobId || !status || !["queued", "running"].includes(status)) {
      return;
    }

    let active = true;

    const poll = async () => {
      try {
        const updated = await getMediaJob(projectId, jobId);

        if (!active) {
          return;
        }

        setMaintenanceJob(updated);

        if (updated.status === "completed") {
          await loadProject(projectId);
        }
      } catch (err) {
        if (active) {
          setMaintenanceError(
            err instanceof Error
              ? err.message
              : "Could not check maintenance job status.",
          );
        }
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
  }, [projectId, maintenanceJob?.job_id, maintenanceJob?.status]);

  async function startProbeJob() {
    if (!projectId) {
      return;
    }

    setMaintenanceError(null);

    try {
      setMaintenanceJob(await startProbe(projectId, false));
    } catch (err) {
      setMaintenanceError(
        err instanceof Error ? err.message : "Could not start probe.",
      );
    }
  }

  async function startThumbnailsJob() {
    if (!projectId) {
      return;
    }

    setMaintenanceError(null);

    try {
      setMaintenanceJob(await startThumbnails(projectId, false));
    } catch (err) {
      setMaintenanceError(
        err instanceof Error
          ? err.message
          : "Could not start thumbnail generation.",
      );
    }
  }

  if (loading) {
    return (
      <HStack>
        <Spinner />
        <Text>Loading project...</Text>
      </HStack>
    );
  }

  if (error || !project) {
    return (
      <Alert status="error">
        <AlertIcon />
        {error ?? "Project not found."}
      </Alert>
    );
  }

  const jobRunning =
    maintenanceJob?.status === "queued" || maintenanceJob?.status === "running";
  const maintenanceProgress =
    maintenanceJob?.progress &&
    !Array.isArray(maintenanceJob.progress) &&
    "completed" in maintenanceJob.progress &&
    "total" in maintenanceJob.progress
      ? (maintenanceJob.progress as {
          current_file?: unknown;
          completed?: unknown;
          total?: unknown;
        })
      : null;

  return (
    <VStack align="stretch" spacing={8}>
      <div>
        <Heading size="lg">{project.name}</Heading>

        <Text mt={2} color="gray.500">
          {project.path}
        </Text>

        {project.timezone && (
          <Text mt={2} fontSize="sm" color="gray.500">
            Timezone: {project.timezone}
          </Text>
        )}
      </div>

      <Box borderWidth="1px" borderRadius="lg" bg="white" p={5}>
        <VStack align="stretch" spacing={4}>
          <Heading size="md">Maintenance</Heading>

          <Text color="gray.600">
            Run probe and thumbnails after imports to populate clip metadata and
            previews.
          </Text>

          <HStack>
            <Button
              colorScheme="blue"
              onClick={() => void startProbeJob()}
              isDisabled={jobRunning}
            >
              Run probe
            </Button>

            <Button
              variant="outline"
              onClick={() => void startThumbnailsJob()}
              isDisabled={jobRunning}
            >
              Generate thumbnails
            </Button>
          </HStack>

          {maintenanceError && (
            <Alert status="error">
              <AlertIcon />
              {maintenanceError}
            </Alert>
          )}

          {maintenanceJob && (
            <Alert
              status={
                maintenanceJob.status === "failed"
                  ? "error"
                  : maintenanceJob.status === "completed"
                    ? "success"
                    : "info"
              }
            >
              <AlertIcon />
              <VStack align="start" spacing={1}>
                <Text fontWeight="semibold">
                  {maintenanceJob.kind === "probe"
                    ? "Probe"
                    : maintenanceJob.kind === "thumbnails"
                      ? "Thumbnails"
                      : "Maintenance"}{" "}
                  {maintenanceJob.status === "queued"
                    ? "queued"
                    : maintenanceJob.status === "running"
                      ? "running"
                      : maintenanceJob.status === "completed"
                        ? "completed"
                        : "failed"}
                </Text>

                {maintenanceProgress && (
                  <Text fontSize="sm">
                    {typeof maintenanceProgress.current_file === "string"
                      ? `${maintenanceProgress.current_file} · `
                      : ""}
                    {typeof maintenanceProgress.completed === "number"
                      ? maintenanceProgress.completed
                      : 0}
                    /
                    {typeof maintenanceProgress.total === "number"
                      ? maintenanceProgress.total
                      : 0}
                  </Text>
                )}

                {maintenanceJob.error && (
                  <Text fontSize="sm">{maintenanceJob.error}</Text>
                )}
              </VStack>
            </Alert>
          )}
        </VStack>
      </Box>

      <SimpleGrid
        columns={{
          base: 1,
          md: 2,
          lg: 4,
        }}
        spacing={4}
      >
        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Clips</StatLabel>
          <StatNumber>{project.stats.clips}</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Edits</StatLabel>
          <StatNumber>{project.stats.edits}</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Renders</StatLabel>
          <StatNumber>{project.stats.renders}</StatNumber>
        </Stat>

        <Stat bg="white" borderWidth="1px" borderRadius="lg" p={5}>
          <StatLabel>Social exports</StatLabel>
          <StatNumber>{project.stats.social_exports}</StatNumber>
        </Stat>
      </SimpleGrid>
    </VStack>
  );
}
