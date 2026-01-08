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
  ScrollView,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Search, Filter, Calendar, X, History as HistoryIcon, Camera, ChevronLeft, Crown, Target } from 'lucide-react-native';
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
  const { isAuthenticated, user } = useAuthStore();
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
        <View style={styles.scanCard}>
          <View style={styles.scanRow}>
            {/* Left side - Icon or Image */}
            {imageUri ? (
              <Image source={{ uri: imageUri }} style={styles.thumbnail} />
            ) : (
              <View style={styles.scanIconBox}>
                <Target size={28} color={colors.textPrimary} />
              </View>
            )}
            
            {/* Middle - Info */}
            <View style={styles.scanInfo}>
              <View style={styles.statusBadge}>
                <Text style={[
                  styles.statusText,
                  item.recommendation === 'HARVEST' ? styles.harvestStatus : styles.passStatus
                ]}>
                  {item.recommendation || 'PASS'}
                </Text>
              </View>
              <Text style={styles.ageText}>
                Age: {item.deer_age || '?'} yrs
              </Text>
              <Text style={styles.pointsText}>
                {item.antler_points || 0} points
              </Text>
              <Text style={styles.dateText}>
                {format(new Date(item.created_at), 'MMM d, yyyy')}
              </Text>
            </View>
            
            {/* Right side - Confidence */}
            <View style={styles.confidenceContainer}>
              <Text style={styles.confidenceValue}>
                {item.confidence || 0}%
              </Text>
              <Text style={styles.confidenceLabel}>confidence</Text>
            </View>
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  // Empty State Component
  const EmptyState = () => (
    <View style={styles.emptyContainer}>
      {/* Camera Icon Circle */}
      <View style={styles.emptyIconCircle}>
        <Camera size={48} color={colors.textMuted} />
      </View>
      
      {/* Title & Description */}
      <Text style={styles.emptyTitle}>Build Your History</Text>
      <Text style={styles.emptyDescription}>
        Every scan you run will appear here with{'\n'}detailed analysis and recommendations
      </Text>
      
      {/* Example Card */}
      <View style={styles.exampleCard}>
        <View style={styles.exampleBadge}>
          <Text style={styles.exampleBadgeText}>EXAMPLE</Text>
        </View>
        
        <View style={styles.exampleContent}>
          {/* Left Icon */}
          <View style={styles.exampleIconBox}>
            <Target size={28} color={colors.textPrimary} />
          </View>
          
          {/* Middle Info */}
          <View style={styles.exampleInfo}>
            <View style={styles.exampleStatusBadge}>
              <Text style={styles.exampleStatusText}>PASS</Text>
            </View>
            <Text style={styles.exampleAgeText}>Age: 3.5 yrs</Text>
            <Text style={styles.examplePointsText}>8 points</Text>
            <Text style={styles.exampleSubText}>Your scans will show here</Text>
          </View>
          
          {/* Right Confidence */}
          <View style={styles.exampleConfidence}>
            <Text style={styles.exampleConfidenceValue}>87%</Text>
            <Text style={styles.exampleConfidenceLabel}>confidence</Text>
          </View>
        </View>
      </View>
      
      {/* CTA Button */}
      <TouchableOpacity 
        style={styles.scanButton}
        onPress={() => router.push('/(tabs)/scan')}
      >
        <Camera size={20} color={colors.background} />
        <Text style={styles.scanButtonText}>Scan Your First Deer</Text>
      </TouchableOpacity>
    </View>
  );

  if (!isAuthenticated) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.header}>
          <TouchableOpacity 
            style={styles.backButton}
            onPress={() => router.back()}
          >
            <ChevronLeft size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.title}>History</Text>
          <View style={styles.headerRight} />
        </View>
        <View style={styles.authRequired}>
          <HistoryIcon size={64} color={colors.textMuted} />
          <Text style={styles.authTitle}>Sign In Required</Text>
          <Text style={styles.authText}>
            Please sign in to view your scan history.
          </Text>
          <TouchableOpacity 
            style={styles.signInButton}
            onPress={() => router.push('/(auth)/login')}
          >
            <Text style={styles.signInButtonText}>Sign In</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity 
          style={styles.backButton}
          onPress={() => router.push('/(tabs)')}
        >
          <ChevronLeft size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.title}>History</Text>
        <TouchableOpacity style={styles.premiumBadge}>
          <Crown size={14} color={colors.primary} />
          <Text style={styles.premiumText}>Premium</Text>
        </TouchableOpacity>
      </View>

      {scans.length > 0 ? (
        <>
          {/* Search & Filters - Only show when there are scans */}
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
              hasActiveFilters ? (
                <View style={styles.noResultsContainer}>
                  <Search size={48} color={colors.textMuted} />
                  <Text style={styles.noResultsTitle}>No Matching Scans</Text>
                  <Text style={styles.noResultsText}>
                    Try adjusting your filters or search query.
                  </Text>
                  <TouchableOpacity onPress={clearFilters}>
                    <Text style={styles.clearFiltersText}>Clear All Filters</Text>
                  </TouchableOpacity>
                </View>
              ) : null
            }
          />
        </>
      ) : (
        <ScrollView 
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.primary}
            />
          }
        >
          <EmptyState />
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  headerRight: {
    width: 40,
  },
  premiumBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.backgroundCard,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    gap: spacing.xs,
  },
  premiumText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
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
  
  // Scan Card Styles
  scanCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  scanRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  scanIconBox: {
    width: 60,
    height: 60,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  thumbnail: {
    width: 60,
    height: 60,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
  },
  scanInfo: {
    flex: 1,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
    marginBottom: 4,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  harvestStatus: {
    color: colors.harvest,
  },
  passStatus: {
    color: colors.primary,
  },
  ageText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  pointsText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  dateText: {
    fontSize: 12,
    color: colors.textMuted,
  },
  confidenceContainer: {
    alignItems: 'flex-end',
  },
  confidenceValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  confidenceLabel: {
    fontSize: 11,
    color: colors.textMuted,
  },

  // Empty State Styles
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xxl,
  },
  emptyIconCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  emptyTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  emptyDescription: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.xl,
  },
  
  // Example Card Styles
  exampleCard: {
    width: '100%',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.xl,
    position: 'relative',
  },
  exampleBadge: {
    position: 'absolute',
    top: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  exampleBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.background,
    letterSpacing: 0.5,
  },
  exampleContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  exampleIconBox: {
    width: 60,
    height: 60,
    borderRadius: borderRadius.md,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  exampleInfo: {
    flex: 1,
  },
  exampleStatusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
    marginBottom: 4,
  },
  exampleStatusText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.harvest,
    letterSpacing: 0.5,
  },
  exampleAgeText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  examplePointsText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  exampleSubText: {
    fontSize: 12,
    color: colors.textMuted,
  },
  exampleConfidence: {
    alignItems: 'flex-end',
  },
  exampleConfidenceValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  exampleConfidenceLabel: {
    fontSize: 11,
    color: colors.textMuted,
  },

  // CTA Button
  scanButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.full,
    gap: spacing.sm,
    width: '100%',
  },
  scanButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },

  // Auth Required State
  authRequired: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  authTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  authText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  signInButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.full,
  },
  signInButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },

  // No Results
  noResultsContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  noResultsTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  noResultsText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
});
