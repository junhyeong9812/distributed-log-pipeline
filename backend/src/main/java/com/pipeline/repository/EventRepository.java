package com.pipeline.repository;

import com.pipeline.entity.EventEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface EventRepository extends JpaRepository<EventEntity, Long> {

    List<EventEntity> findByUserId(String userId);

    List<EventEntity> findByEventType(String eventType);

    @Query("SELECT e FROM EventEntity e WHERE e.timestamp BETWEEN :start AND :end")
    List<EventEntity> findByTimestampRange(@Param("start") Double start, @Param("end") Double end);

    @Query("SELECT e.eventType, COUNT(e) FROM EventEntity e GROUP BY e.eventType")
    List<Object[]> countByEventType();

    long countByEventType(String eventType);
}
