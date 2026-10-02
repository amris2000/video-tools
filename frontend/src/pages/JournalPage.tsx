import {
  Alert,
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertIcon,
  Box,
  Button,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  Input,
  SimpleGrid,
  Spinner,
  Stack,
  Tag,
  Text,
  Textarea,
  VStack,
  useDisclosure,
} from "@chakra-ui/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  createJournalEntry,
  deleteJournalEntry,
  getJournalEntries,
  updateJournalEntry,
  type JournalEntry,
  type JournalEntryPayload,
} from "../api/workflows";

type JournalFormState = {
  date: string;
  activity: string;
  location: string;
  start_time: string;
  end_time: string;
  tags: string;
  highlight: string;
  notes: string;
};

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(): JournalFormState {
  return {
    date: todayDate(),
    activity: "",
    location: "",
    start_time: "",
    end_time: "",
    tags: "",
    highlight: "",
    notes: "",
  };
}

function toPayload(form: JournalFormState): JournalEntryPayload {
  return {
    date: form.date,
    activity: form.activity.trim(),
    location: form.location.trim() || null,
    start_time: form.start_time || null,
    end_time: form.end_time || null,
    tags: form.tags
      .split(",")
      .map((tag) => tag.trim().toLowerCase())
      .filter(Boolean),
    highlight: form.highlight.trim() || null,
    notes: form.notes.trim() || null,
  };
}

function fromEntry(entry: JournalEntry): JournalFormState {
  return {
    date: entry.date,
    activity: entry.activity,
    location: entry.location ?? "",
    start_time: entry.start_time ?? "",
    end_time: entry.end_time ?? "",
    tags: entry.tags.join(", "),
    highlight: entry.highlight ?? "",
    notes: entry.notes ?? "",
  };
}

export function JournalPage() {
  const { projectId } = useParams();
  const activeProjectId = projectId ?? "";

  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<JournalFormState>(() => emptyForm());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<JournalEntry | null>(null);

  const { isOpen, onOpen, onClose } = useDisclosure();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    getJournalEntries(activeProjectId, controller.signal)
      .then((value) => {
        if (active) setEntries(value);
      })
      .catch((reason) => {
        if (active && !controller.signal.aborted) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load journal entries.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [activeProjectId]);

  const sortedEntries = useMemo(
    () =>
      [...entries].sort((a, b) => {
        const keyA = `${a.date}|${a.start_time ?? ""}|${a.logged_at}`;
        const keyB = `${b.date}|${b.start_time ?? ""}|${b.logged_at}`;
        return keyA.localeCompare(keyB);
      }),
    [entries],
  );

  function resetForm() {
    setForm(emptyForm());
    setEditingId(null);
  }

  async function handleSubmit() {
    const payload = toPayload(form);

    if (!payload.activity) {
      setError("Activity is required.");
      return;
    }

    setSaving(true);
    setError("");

    try {
      if (editingId) {
        const updated = await updateJournalEntry(
          activeProjectId,
          editingId,
          payload,
        );

        setEntries((current) =>
          current.map((entry) => (entry.id === updated.id ? updated : entry)),
        );
      } else {
        const created = await createJournalEntry(activeProjectId, payload);
        setEntries((current) => [...current, created]);
      }

      resetForm();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not save journal entry.",
      );
    } finally {
      setSaving(false);
    }
  }

  function startEdit(entry: JournalEntry) {
    setForm(fromEntry(entry));
    setEditingId(entry.id);
    setError("");
  }

  function requestDelete(entry: JournalEntry) {
    setPendingDelete(entry);
    setError("");
    onOpen();
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }

    setDeleting(true);
    setError("");

    try {
      await deleteJournalEntry(activeProjectId, pendingDelete.id);
      setEntries((current) =>
        current.filter((entry) => entry.id !== pendingDelete.id),
      );
      if (editingId === pendingDelete.id) {
        resetForm();
      }
      setPendingDelete(null);
      onClose();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not delete journal entry.",
      );
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <HStack role="status">
        <Spinner />
        <Text>Loading journal…</Text>
      </HStack>
    );
  }

  return (
    <VStack align="stretch" spacing={6}>
      <Box>
        <Heading size="lg">Journal</Heading>
        <Text color="gray.600">
          Track shoot notes, locations, highlights, and timing.
        </Text>
      </Box>

      {error && (
        <Alert status="error">
          <AlertIcon />
          {error}
        </Alert>
      )}

      <SimpleGrid columns={{ base: 1, xl: 2 }} spacing={6} alignItems="start">
        <VStack align="stretch" spacing={3}>
          <Heading size="md">Entries</Heading>

          {!sortedEntries.length ? (
            <Text color="gray.600">No journal entries yet.</Text>
          ) : (
            sortedEntries.map((entry) => (
              <Box
                key={entry.id}
                borderWidth="1px"
                borderRadius="lg"
                bg="white"
                p={4}
              >
                <VStack align="stretch" spacing={2}>
                  <HStack justify="space-between" align="start">
                    <Box>
                      <Text fontWeight="bold">
                        {entry.activity || "Untitled activity"}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        {entry.date}
                        {entry.start_time ? ` ${entry.start_time}` : ""}
                        {entry.end_time ? `-${entry.end_time}` : ""}
                      </Text>
                    </Box>

                    <HStack>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startEdit(entry)}
                      >
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        colorScheme="red"
                        variant="ghost"
                        onClick={() => requestDelete(entry)}
                      >
                        Delete
                      </Button>
                    </HStack>
                  </HStack>

                  {entry.location && (
                    <Text color="gray.700">Location: {entry.location}</Text>
                  )}
                  {entry.highlight && (
                    <Text color="gray.700">Highlight: {entry.highlight}</Text>
                  )}
                  {entry.notes && (
                    <Text whiteSpace="pre-wrap">{entry.notes}</Text>
                  )}

                  {!!entry.tags.length && (
                    <HStack spacing={2} flexWrap="wrap">
                      {entry.tags.map((tag) => (
                        <Tag key={`${entry.id}-${tag}`}>{tag}</Tag>
                      ))}
                    </HStack>
                  )}
                </VStack>
              </Box>
            ))
          )}
        </VStack>

        <Box borderWidth="1px" borderRadius="lg" bg="white" p={5}>
          <VStack align="stretch" spacing={4}>
            <Heading size="sm">
              {editingId ? "Edit journal entry" : "Add journal entry"}
            </Heading>

            <Stack direction={{ base: "column", md: "row" }} spacing={4}>
              <FormControl isRequired>
                <FormLabel>Date</FormLabel>
                <Input
                  type="date"
                  value={form.date}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      date: event.target.value,
                    }))
                  }
                />
              </FormControl>

              <FormControl>
                <FormLabel>Start time</FormLabel>
                <Input
                  type="time"
                  value={form.start_time}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      start_time: event.target.value,
                    }))
                  }
                />
              </FormControl>

              <FormControl>
                <FormLabel>End time</FormLabel>
                <Input
                  type="time"
                  value={form.end_time}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      end_time: event.target.value,
                    }))
                  }
                />
              </FormControl>
            </Stack>

            <FormControl isRequired>
              <FormLabel>Activity</FormLabel>
              <Input
                placeholder="Morning surf session"
                value={form.activity}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    activity: event.target.value,
                  }))
                }
              />
            </FormControl>

            <FormControl>
              <FormLabel>Location</FormLabel>
              <Input
                placeholder="Praia do Amado"
                value={form.location}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    location: event.target.value,
                  }))
                }
              />
            </FormControl>

            <FormControl>
              <FormLabel>Tags (comma separated)</FormLabel>
              <Input
                placeholder="sunset, b-roll, timelapse"
                value={form.tags}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    tags: event.target.value,
                  }))
                }
              />
            </FormControl>

            <FormControl>
              <FormLabel>Highlight</FormLabel>
              <Input
                placeholder="Best aerial clip near the cliff"
                value={form.highlight}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    highlight: event.target.value,
                  }))
                }
              />
            </FormControl>

            <FormControl>
              <FormLabel>Notes</FormLabel>
              <Textarea
                rows={4}
                value={form.notes}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    notes: event.target.value,
                  }))
                }
              />
            </FormControl>

            <HStack justify="flex-end">
              {editingId && (
                <Button variant="ghost" onClick={resetForm} isDisabled={saving}>
                  Cancel edit
                </Button>
              )}
              <Button
                colorScheme="brand"
                onClick={() => void handleSubmit()}
                isLoading={saving}
              >
                {editingId ? "Update entry" : "Add entry"}
              </Button>
            </HStack>
          </VStack>
        </Box>
      </SimpleGrid>

      <AlertDialog
        isOpen={isOpen}
        leastDestructiveRef={cancelRef}
        onClose={() => {
          if (!deleting) {
            setPendingDelete(null);
            onClose();
          }
        }}
        isCentered
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete journal entry
            </AlertDialogHeader>
            <AlertDialogBody>
              Are you sure you want to delete this entry?
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button
                ref={cancelRef}
                onClick={() => {
                  setPendingDelete(null);
                  onClose();
                }}
                isDisabled={deleting}
              >
                Cancel
              </Button>
              <Button
                colorScheme="red"
                ml={3}
                onClick={() => void confirmDelete()}
                isLoading={deleting}
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
