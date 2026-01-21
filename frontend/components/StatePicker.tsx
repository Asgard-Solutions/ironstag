/**
 * State Picker Component
 * 
 * Reusable US state selector for region-specific calibration.
 * Used in Profile (home state) and Scan (hunting location override).
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  FlatList,
  TextInput,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { X, Search, MapPin, Check } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../constants/theme';

// US States with abbreviations
export const US_STATES = [
  { code: 'AL', name: 'Alabama' },
  { code: 'AK', name: 'Alaska' },
  { code: 'AZ', name: 'Arizona' },
  { code: 'AR', name: 'Arkansas' },
  { code: 'CA', name: 'California' },
  { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' },
  { code: 'DE', name: 'Delaware' },
  { code: 'FL', name: 'Florida' },
  { code: 'GA', name: 'Georgia' },
  { code: 'HI', name: 'Hawaii' },
  { code: 'ID', name: 'Idaho' },
  { code: 'IL', name: 'Illinois' },
  { code: 'IN', name: 'Indiana' },
  { code: 'IA', name: 'Iowa' },
  { code: 'KS', name: 'Kansas' },
  { code: 'KY', name: 'Kentucky' },
  { code: 'LA', name: 'Louisiana' },
  { code: 'ME', name: 'Maine' },
  { code: 'MD', name: 'Maryland' },
  { code: 'MA', name: 'Massachusetts' },
  { code: 'MI', name: 'Michigan' },
  { code: 'MN', name: 'Minnesota' },
  { code: 'MS', name: 'Mississippi' },
  { code: 'MO', name: 'Missouri' },
  { code: 'MT', name: 'Montana' },
  { code: 'NE', name: 'Nebraska' },
  { code: 'NV', name: 'Nevada' },
  { code: 'NH', name: 'New Hampshire' },
  { code: 'NJ', name: 'New Jersey' },
  { code: 'NM', name: 'New Mexico' },
  { code: 'NY', name: 'New York' },
  { code: 'NC', name: 'North Carolina' },
  { code: 'ND', name: 'North Dakota' },
  { code: 'OH', name: 'Ohio' },
  { code: 'OK', name: 'Oklahoma' },
  { code: 'OR', name: 'Oregon' },
  { code: 'PA', name: 'Pennsylvania' },
  { code: 'RI', name: 'Rhode Island' },
  { code: 'SC', name: 'South Carolina' },
  { code: 'SD', name: 'South Dakota' },
  { code: 'TN', name: 'Tennessee' },
  { code: 'TX', name: 'Texas' },
  { code: 'UT', name: 'Utah' },
  { code: 'VT', name: 'Vermont' },
  { code: 'VA', name: 'Virginia' },
  { code: 'WA', name: 'Washington' },
  { code: 'WV', name: 'West Virginia' },
  { code: 'WI', name: 'Wisconsin' },
  { code: 'WY', name: 'Wyoming' },
];

// Get state name from code
export function getStateName(code: string | null | undefined): string {
  if (!code) return 'Not Set';
  const state = US_STATES.find(s => s.code === code.toUpperCase());
  return state ? state.name : code;
}

interface StatePickerProps {
  visible: boolean;
  selectedState: string | null;
  onSelect: (stateCode: string | null) => void;
  onClose: () => void;
  title?: string;
  allowClear?: boolean;
}

export function StatePicker({
  visible,
  selectedState,
  onSelect,
  onClose,
  title = 'Select State',
  allowClear = true,
}: StatePickerProps) {
  const insets = useSafeAreaInsets();
  const [searchQuery, setSearchQuery] = useState('');

  const filteredStates = US_STATES.filter(state => 
    state.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    state.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelect = (stateCode: string) => {
    onSelect(stateCode);
    onClose();
    setSearchQuery('');
  };

  const handleClear = () => {
    onSelect(null);
    onClose();
    setSearchQuery('');
  };

  const renderItem = ({ item }: { item: typeof US_STATES[0] }) => {
    const isSelected = selectedState?.toUpperCase() === item.code;
    
    return (
      <TouchableOpacity
        style={[styles.stateItem, isSelected && styles.stateItemSelected]}
        onPress={() => handleSelect(item.code)}
        activeOpacity={0.7}
      >
        <View style={styles.stateInfo}>
          <Text style={[styles.stateCode, isSelected && styles.stateTextSelected]}>
            {item.code}
          </Text>
          <Text style={[styles.stateName, isSelected && styles.stateTextSelected]}>
            {item.name}
          </Text>
        </View>
        {isSelected && (
          <Check size={20} color={colors.primary} />
        )}
      </TouchableOpacity>
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <X size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.title}>{title}</Text>
          <View style={styles.closeButton} />
        </View>

        {/* Search */}
        <View style={styles.searchContainer}>
          <Search size={20} color={colors.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search states..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCorrect={false}
          />
        </View>

        {/* Clear option */}
        {allowClear && selectedState && (
          <TouchableOpacity style={styles.clearButton} onPress={handleClear}>
            <X size={16} color={colors.error} />
            <Text style={styles.clearButtonText}>Clear Selection</Text>
          </TouchableOpacity>
        )}

        {/* State list */}
        <FlatList
          data={filteredStates}
          keyExtractor={(item) => item.code}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        />
      </View>
    </Modal>
  );
}

interface StateDisplayProps {
  state: string | null | undefined;
  onPress: () => void;
  label?: string;
  placeholder?: string;
  compact?: boolean;
}

export function StateDisplay({
  state,
  onPress,
  label = 'State',
  placeholder = 'Select State',
  compact = false,
}: StateDisplayProps) {
  const stateName = state ? getStateName(state) : null;

  if (compact) {
    return (
      <TouchableOpacity style={styles.compactButton} onPress={onPress}>
        <MapPin size={16} color={state ? colors.primary : colors.textMuted} />
        <Text style={[styles.compactText, state && styles.compactTextSelected]}>
          {state || placeholder}
        </Text>
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity style={styles.displayButton} onPress={onPress}>
      <View style={styles.displayContent}>
        <Text style={styles.displayLabel}>{label}</Text>
        <View style={styles.displayValue}>
          <MapPin size={18} color={state ? colors.primary : colors.textMuted} />
          <Text style={[styles.displayText, !state && styles.displayPlaceholder]}>
            {stateName || placeholder}
          </Text>
        </View>
      </View>
      <Text style={styles.displayArrow}>›</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  closeButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.backgroundCard,
    margin: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchInput: {
    flex: 1,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    fontSize: 16,
    color: colors.textPrimary,
  },
  clearButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
  },
  clearButtonText: {
    fontSize: 14,
    color: colors.error,
  },
  listContent: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.xl,
  },
  stateItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.xs,
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  stateItemSelected: {
    borderColor: colors.primary,
    backgroundColor: 'rgba(200, 162, 74, 0.1)',
  },
  stateInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  stateCode: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
    width: 30,
  },
  stateName: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  stateTextSelected: {
    color: colors.primary,
  },
  // Display button styles
  displayButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.backgroundCard,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  displayContent: {
    flex: 1,
  },
  displayLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 4,
  },
  displayValue: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  displayText: {
    fontSize: 16,
    color: colors.textPrimary,
    fontWeight: '500',
  },
  displayPlaceholder: {
    color: colors.textMuted,
    fontWeight: '400',
  },
  displayArrow: {
    fontSize: 24,
    color: colors.textMuted,
    marginLeft: spacing.sm,
  },
  // Compact styles
  compactButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  compactText: {
    fontSize: 14,
    color: colors.textMuted,
  },
  compactTextSelected: {
    color: colors.primary,
    fontWeight: '500',
  },
});
