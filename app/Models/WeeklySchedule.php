<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * @OA\Schema(
 *     title="WeeklySchedule",
 *     description="WeeklySchedule model",
 *     @OA\Xml(
 *         name="WeeklySchedule"
 *     )
 * )
 */

class WeeklySchedule extends Model
{
    use HasFactory;

    protected $casts=[
        'price'=> 'int64'
    ];

    protected $table = 'weekly_schedule';

    /**
     * Get the reservations for the weekly schedule.
     */
    public function Reservations(): HasMany
    {
        return $this->hasMany(Reservation::class);
    }

    /**
     * Get the chairs for the  weekly schedule.
     */
    public function chairs(): HasMany
    {
        return $this->hasMany(Chairs::class)->select(['id', 'chairs']);
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
     *     title="source ctiy",
     *     description="source ctiy",
     *     format="string",
     *     example=esf
     * )
     *
     * @var string
     */
    private string $source_city_id;

    /**
     * @OA\Property(
     *     title="source terminal",
     *     description="source terminal",
     *     format="string",
     *     example=esf
     * )
     *
     * @var string
     */
    private string $source_terminal_id;

    /**
     * @OA\Property(
     *     title="destination city",
     *     description="destination city",
     *     format="string",
     *     example=esf
     * )
     *
     * @var string
     */
    private string $destination_city_id;

    /**
     * @OA\Property(
     *     title="destination terminal",
     *     description="destination terminal",
     *     format="string",
     *     example=esf
     * )
     *
     * @var string
     */
    private string $destination_terminal_id;

    /**
     * @OA\Property(
     *     title="moving day number",
     *     description="moving day number",
     *     format="int16",
     *     example=0
     * )
     *
     * @var integer
     */
    private int $moving_day_number;

    /**
     * @OA\Property(
     *     title="moving day number",
     *     description="moving day number",
     *     format="int64",
     *     example=0
     * )
     *
     * @var integer
     */
    private int $moving_time_seconds;

    /**
     * @OA\Property(
     *     title="traveling time",
     *     description="traveling time",
     *     format="int32",
     *     example=0
     * )
     *
     * @var integer
     */
    private int $traveling_time;

    /**
     * @OA\Property(
     *     title="capacity",
     *     description="bus capacity",
     *     format="int32",
     *     example=0
     * )
     *
     * @var integer
     */
    private int $capacity;

    /**
     * @OA\Property(
     *     title="capacity",
     *     description="bus type such as vip and etc.",
     *     format="string",
     *     example=0
     * )
     *
     * @var string
     */
    private string $bus_type;

    /**
     * @OA\Property(
     *     title="price",
     *     description="bus type such as vip and etc.",
     *     format="int64",
     *     example=0
     * )
     *
     * @var integer
     */
    private $price;
}
