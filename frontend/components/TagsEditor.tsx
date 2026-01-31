import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Modal,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { Tag, X, Plus, Check } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../constants/theme';
import { scanAPI } from '../utils/api';

interface TagsEditorProps {
  scanId: string;
  initialTags: string[];
  onTagsUpdated?: (tags: string[]) => void;
}

// Common tag suggestions for deer hunting
const SUGGESTED_TAGS = [
  'Trophy Buck',
  'Young Buck',
  'Mature Doe',
  'Field Photo',
  'Trail Cam',
  'Opening Day',
  'Rut',
  'Pre-Rut',
  'Post-Rut',
  'Morning Hunt',
  'Evening Hunt',
  'Public Land',
  'Private Land',
  'Food Plot',
  'Oak Ridge',
  'Creek Bottom',
  'Corn Field',
  'Bedding Area',
];

export function TagsEditor({ scanId, initialTags, onTagsUpdated }: TagsEditorProps) {
  const [tags, setTags] = useState<string[]>(initialTags || []);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [allUserTags, setAllUserTags] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [loadingTags, setLoadingTags] = useState(false);

  // Load user's existing tags for suggestions
  useEffect(() => {
    loadAllUserTags();
  }, []);

  const loadAllUserTags = async () => {
    setLoadingTags(true);
    try {
      const response = await scanAPI.getAllTags();
      setAllUserTags(response.data.tags || []);
    } catch (error) {
      console.error('Failed to load user tags:', error);
    } finally {
      setLoadingTags(false);
    }
  };

  const saveTagsToServer = async (newTags: string[]) => {
    setSaving(true);
    try {
      await scanAPI.updateTags(scanId, newTags);
      setTags(newTags);
      onTagsUpdated?.(newTags);
    } catch (error) {
      console.error('Failed to save tags:', error);
    } finally {
      setSaving(false);
    }
  };

  const addTag = async (tagToAdd: string) => {
    const cleanTag = tagToAdd.trim();
    if (!cleanTag || tags.includes(cleanTag)) return;
    
    const newTags = [...tags, cleanTag];
    await saveTagsToServer(newTags);
    setNewTag('');
    setShowAddModal(false);
  };

  const removeTag = async (tagToRemove: string) => {
    const newTags = tags.filter(t => t !== tagToRemove);
    await saveTagsToServer(newTags);
  };

  // Combine user's tags, suggested tags, and filter out already-added
  const availableSuggestions = [...new Set([...allUserTags, ...SUGGESTED_TAGS])]
    .filter(t => !tags.includes(t))
    .sort();

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Tag size={16} color={colors.textSecondary} />
          <Text style={styles.title}>Tags</Text>
        </View>
        <TouchableOpacity 
          style={styles.addButton}
          onPress={() => setShowAddModal(true)}
        >
          <Plus size={16} color={colors.primary} />
          <Text style={styles.addButtonText}>Add</Text>
        </TouchableOpacity>
      </View>

      {/* Current Tags */}
      {tags.length > 0 ? (
        <View style={styles.tagsList}>
          {tags.map((tag, index) => (
            <View key={index} style={styles.tag}>
              <Text style={styles.tagText}>{tag}</Text>
              <TouchableOpacity 
                onPress={() => removeTag(tag)}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                disabled={saving}
              >
                <X size={14} color={colors.textMuted} />
              </TouchableOpacity>
            </View>
          ))}
          {saving && (
            <ActivityIndicator size="small" color={colors.primary} style={styles.savingIndicator} />
          )}
        </View>
      ) : (
        <Text style={styles.emptyText}>
          No tags yet. Add tags to organize your scans.
        </Text>
      )}

      {/* Add Tag Modal */}
      <Modal
        visible={showAddModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowAddModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={styles.modalContent}>
            {/* Modal Header */}
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add Tag</Text>
              <TouchableOpacity onPress={() => setShowAddModal(false)}>
                <X size={24} color={colors.textPrimary} />
              </TouchableOpacity>
            </View>

            {/* Custom Tag Input */}
            <View style={styles.inputRow}>
              <TextInput
                style={styles.input}
                value={newTag}
                onChangeText={setNewTag}
                placeholder="Enter custom tag..."
                placeholderTextColor={colors.textMuted}
                autoFocus
                returnKeyType="done"
                onSubmitEditing={() => addTag(newTag)}
              />
              <TouchableOpacity 
                style={[styles.submitButton, !newTag.trim() && styles.submitButtonDisabled]}
                onPress={() => addTag(newTag)}
                disabled={!newTag.trim() || saving}
              >
                {saving ? (
                  <ActivityIndicator size="small" color={colors.white} />
                ) : (
                  <Check size={20} color={colors.white} />
                )}
              </TouchableOpacity>
            </View>

            {/* Suggestions */}
            <Text style={styles.suggestionsTitle}>Suggestions</Text>
            {loadingTags ? (
              <ActivityIndicator size="small" color={colors.primary} style={styles.loadingIndicator} />
            ) : (
              <FlatList
                data={availableSuggestions}
                keyExtractor={(item) => item}
                numColumns={2}
                columnWrapperStyle={styles.suggestionsRow}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={styles.suggestionChip}
                    onPress={() => addTag(item)}
                    disabled={saving}
                  >
                    <Text style={styles.suggestionChipText}>{item}</Text>
                  </TouchableOpacity>
                )}
                ListEmptyComponent={
                  <Text style={styles.noSuggestionsText}>
                    All suggestions have been added.
                  </Text>
                }
                style={styles.suggestionsList}
              />
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  addButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.primary + '20',
    borderRadius: borderRadius.sm,
  },
  addButtonText: {
    fontSize: 13,
    fontWeight: '500',
    color: colors.primary,
  },
  tagsList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    alignItems: 'center',
  },
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.backgroundCard,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tagText: {
    fontSize: 13,
    color: colors.textPrimary,
  },
  savingIndicator: {
    marginLeft: spacing.sm,
  },
  emptyText: {
    fontSize: 13,
    color: colors.textMuted,
    fontStyle: 'italic',
  },

  // Modal styles
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  modalContent: {
    backgroundColor: colors.background,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    padding: spacing.lg,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.lg,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  inputRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  input: {
    flex: 1,
    height: 48,
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    fontSize: 16,
    color: colors.textPrimary,
    borderWidth: 1,
    borderColor: colors.border,
  },
  submitButton: {
    width: 48,
    height: 48,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  submitButtonDisabled: {
    backgroundColor: colors.textMuted,
    opacity: 0.5,
  },
  suggestionsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  loadingIndicator: {
    marginVertical: spacing.md,
  },
  suggestionsList: {
    maxHeight: 300,
  },
  suggestionsRow: {
    justifyContent: 'flex-start',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  suggestionChip: {
    backgroundColor: colors.backgroundCard,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.border,
    maxWidth: '48%',
  },
  suggestionChipText: {
    fontSize: 13,
    color: colors.textPrimary,
  },
  noSuggestionsText: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
    paddingVertical: spacing.md,
  },
});

export default TagsEditor;
