import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Image,
  TextInput,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Search, Filter, Calendar, X, History as HistoryIcon } from 'lucide-react-native';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { format } from 'date-fns';

interface Scan {
  id: string;
  local_image_id: string;
  deer_age: number | null;
  deer_type: string | null;
  deer_sex: string | null;
  antler_points: number | null;
  body_condition: string | null;
  confidence: number | null;
  recommendation: string | null;
  notes: string | null;
  created_at: string;
}

export default function HistoryScreen() {
  const insets = useSafeAreaInsets();
  const { isAuthenticated } = useAuthStore();
  const { getImage, isLoaded } = useImageStore();
  
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    deer_sex: '',
    recommendation: '',
  });

  const loadScans = async () => {
    if (!isAuthenticated) return;
    try {
      const params: any = {};
      if (filters.deer_sex) params.deer_sex = filters.deer_sex;
      if (filters.recommendation) params.recommendation = filters.recommendation;
      
      const response = await scanAPI.getScans(params);
      setScans(response.data);
    } catch (error) {
      console.error('Failed to load scans:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScans();
  }, [isAuthenticated, filters]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadScans();
    setRefreshing(false);
  };

  const filteredScans = scans.filter((scan) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      scan.deer_type?.toLowerCase().includes(query) ||
      scan.deer_sex?.toLowerCase().includes(query) ||
      scan.notes?.toLowerCase().includes(query) ||
      scan.body_condition?.toLowerCase().includes(query)
    );
  });

  const clearFilters = () => {
    setFilters({ deer_sex: '', recommendation: '' });
    setSearchQuery('');
  };

  const hasActiveFilters = filters.deer_sex || filters.recommendation || searchQuery;

  const renderScanCard = ({ item }: { item: Scan }) => {
    const imageUri = getImage(item.local_image_id);
    
    return (
      <TouchableOpacity
        activeOpacity={0.8}
        onPress={() => router.push(`/scan-result/${item.id}`)}
      >
        <Card style={styles.scanCard}>
          <View style={styles.scanRow}>
            {imageUri ? (
              <Image source={{ uri: imageUri }} style={styles.thumbnail} />
            ) : (
              <View style={styles.placeholderImage}>
                <HistoryIcon size={24} color={colors.textMuted} />
              </View>
            )}
            <View style={styles.scanInfo}>
              <View style={styles.scanHeader}>
                <Text style={styles.scanType}>
                  {item.deer_type || 'Unknown Type'}
                </Text>
                <Badge
                  text={item.recommendation || 'N/A'}
                  variant={item.recommendation === 'HARVEST' ? 'harvest' : 'pass'}
                  size="small"
                />
              </View>
              <Text style={styles.scanDetails}>
                {item.deer_sex || 'Unknown'} • Age: {item.deer_age || '?'} yrs
                {item.antler_points && ` • ${item.antler_points} pts`}
              </Text>
              <View style={styles.scanFooter}>
                <Text style={styles.scanDate}>
                  {format(new Date(item.created_at), 'MMM d, yyyy')}
                </Text>
                {item.confidence && (
                  <Text style={styles.confidence}>
                    {item.confidence}% confidence
                  </Text>
                )}
              </View>
            </View>
          </View>
        </Card>
      </TouchableOpacity>
    );
  };

  if (!isAuthenticated) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.emptyState}>
          <HistoryIcon size={64} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>Sign In Required</Text>
          <Text style={styles.emptyText}>
            Please sign in to view your scan history.
          </Text>
          <Button
            title="Sign In"
            onPress={() => router.push('/(auth)/login')}
          />
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Scan History</Text>
      </View>

      {/* Search & Filters */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Search size={20} color={colors.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search scans..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery && (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <X size={18} color={colors.textMuted} />
            </TouchableOpacity>
          )}
        </View>
        <TouchableOpacity
          style={[styles.filterButton, hasActiveFilters && styles.filterButtonActive]}
          onPress={() => setShowFilters(!showFilters)}
        >
          <Filter size={20} color={hasActiveFilters ? colors.background : colors.textPrimary} />
        </TouchableOpacity>
      </View>

      {/* Filter Options */}
      {showFilters && (
        <View style={styles.filterOptions}>
          <View style={styles.filterRow}>
            <Text style={styles.filterLabel}>Sex:</Text>
            {['', 'Buck', 'Doe'].map((sex) => (
              <TouchableOpacity
                key={sex || 'all'}
                style={[
                  styles.filterChip,
                  filters.deer_sex === sex && styles.filterChipActive,
                ]}
                onPress={() => setFilters({ ...filters, deer_sex: sex })}
              >
                <Text
                  style={[
                    styles.filterChipText,
                    filters.deer_sex === sex && styles.filterChipTextActive,
                  ]}
                >
                  {sex || 'All'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.filterRow}>
            <Text style={styles.filterLabel}>Rec:</Text>
            {['', 'HARVEST', 'PASS'].map((rec) => (
              <TouchableOpacity
                key={rec || 'all'}
                style={[
                  styles.filterChip,
                  filters.recommendation === rec && styles.filterChipActive,
                ]}
                onPress={() => setFilters({ ...filters, recommendation: rec })}
              >
                <Text
                  style={[
                    styles.filterChipText,
                    filters.recommendation === rec && styles.filterChipTextActive,
                  ]}
                >
                  {rec || 'All'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          {hasActiveFilters && (
            <TouchableOpacity style={styles.clearFilters} onPress={clearFilters}>
              <Text style={styles.clearFiltersText}>Clear All Filters</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Scan List */}
      <FlatList
        data={filteredScans}
        keyExtractor={(item) => item.id}
        renderItem={renderScanCard}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <HistoryIcon size={48} color={colors.textMuted} />
            <Text style={styles.emptyTitle}>
              {hasActiveFilters ? 'No Matching Scans' : 'No Scans Yet'}
            </Text>
            <Text style={styles.emptyText}>
              {hasActiveFilters
                ? 'Try adjusting your filters or search query.'
                : 'Start by scanning your first deer!'}
            </Text>
            {!hasActiveFilters && (
              <Button
                title="Scan a Deer"
                onPress={() => router.push('/(tabs)/scan')}
                style={styles.emptyButton}
              />
            )}
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  searchContainer: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  searchBar: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  searchInput: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 16,
    paddingVertical: spacing.md,
  },
  filterButton: {
    width: 48,
    height: 48,
    borderRadius: borderRadius.md,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  filterButtonActive: {
    backgroundColor: colors.primary,
  },
  filterOptions: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    gap: spacing.sm,
  },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  filterLabel: {
    color: colors.textSecondary,
    fontSize: 14,
    width: 40,
  },
  filterChip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.full,
    backgroundColor: colors.backgroundCard,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
  },
  filterChipText: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  filterChipTextActive: {
    color: colors.background,
    fontWeight: '600',
  },
  clearFilters: {
    alignSelf: 'flex-start',
    marginTop: spacing.xs,
  },
  clearFiltersText: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '500',
  },
  listContent: {
    padding: spacing.lg,
    paddingTop: 0,
    gap: spacing.md,
  },
  scanCard: {
    padding: spacing.md,
  },
  scanRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  thumbnail: {
    width: 80,
    height: 80,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
  },
  placeholderImage: {
    width: 80,
    height: 80,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scanInfo: {
    flex: 1,
    justifyContent: 'space-between',
  },
  scanHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  scanType: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scanDetails: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  scanFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  scanDate: {
    fontSize: 12,
    color: colors.textMuted,
  },
  confidence: {
    fontSize: 12,
    color: colors.primary,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
    marginTop: spacing.xxl,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  emptyText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  emptyButton: {
    minWidth: 200,
  },
});
