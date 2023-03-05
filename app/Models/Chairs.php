<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * @OA\Schema(
 *     title="Chairs",
 *     description="Chairs model",
 *     @OA\Xml(
 *         name="Chairs"
 *     )
 * )
 */
class Chairs extends Model
{
    use HasFactory;

    protected $table = 'bus_empty_chairs';
    protected $casts = [
        'chairs' => "array",
    ];

    public function WeeklySchedule(): BelongsTo
    {
        return $this->belongsTo(WeeklySchedule::class);
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
     *     description="ID",
     *     format="int64",
     *     example=1
     * )
     *
     * @var integer
     */
    private int $ws_id;

    /**
     * @OA\Property(
     *     title="Chairs",
     *     description="array of chairs are empty",
     *     format="array",
     *     example=1
     * )
     *
     * @var array
     */
    private array $chairs;

    /**
     * @OA\Property(
     *     title="date",
     *     description="date of teravelling",
     *     format="string",
     *     example=1
     * )
     *
     * @var string
     */
    private string $date;

}
