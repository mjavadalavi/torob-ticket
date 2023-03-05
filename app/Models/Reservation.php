<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasOne;

/**
 * @OA\Schema(
 *     title="Reservation",
 *     description="Reservation model",
 *     @OA\Xml(
 *         name="Reservation"
 *     )
 * )
 */
class Reservation extends Model
{
    use HasFactory;

    protected $table = 'reservation';

    protected $casts = [
        'chairs' => "array"
    ];

    public function WeeklySchedule(): BelongsTo
    {
        return $this->belongsTo(WeeklySchedule::class);
    }

    /**
     * Get buy for the reservation.
     */
    public function buys(): HasOne
    {
        return $this->hasOne(Buy::class);
    }

    public function chairs(): BelongsTo
    {
        return $this->belongsTo(Chairs::class);
    }

    /**
     * @OA\Property(
     *     title="ID",
     *     description="ID",
     *     format="int64",
     *     example=1
     * )
     *
     * @var integer
     */
    private int $id;

    /**
     * @OA\Property(
     *     title="ID",
     *     description="WeeklyScheduleID",
     *     format="int64",
     *     example=1
     * )
     *
     * @var integer
     */
    private int $ws_id;

    /**
     * @OA\Property(
     *     title="ID",
     *     description="ChairID",
     *     format="int64",
     *     example=1
     * )
     *
     * @var integer
     */
    private int $chair_id;

    /**
     * @OA\Property(
     *     title="PassengerCount",
     *     description="count of passengers",
     *     format="int64",
     *     example=1
     * )
     *
     * @var integer
     */
    private int $passenger_count;

    /**
     * @OA\Property(
     *     title="PassengerCount",
     *     description="an array of chairs reserved by passenger",
     *     format="array",
     *     example=[1,2,3,4]
     * )
     *
     * @var array
     */
    private array $chairs;

    /**
     * @OA\Property(
     *     title="status",
     *     description="Status of item such as pending, success, cancel and expired",
     *     format="array",
     *     example=-1
     * )
     *
     * @var int
     */
    private int $status;

}
